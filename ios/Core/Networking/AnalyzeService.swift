import Foundation

struct AnalyzeErrorResponse: Decodable {
    let code: String
    let message: String
    let videoId: String?
}

private struct AnalyzeErrorEnvelope: Decodable {
    let error: AnalyzeErrorResponse
}

protocol AnalyzeService {
    func analyzeYouTube(
        title: String,
        youtubeUrl: String,
        onProgress: @escaping @Sendable (AnalyzeProgressUpdate) -> Void
    ) async throws -> AnalyzeResponse
}

enum AnalyzeServiceError: Error, LocalizedError {
    case invalidBaseURL(String)
    case invalidHTTPResponse
    case serverError(statusCode: Int, message: String)
    case backendError(code: String, message: String, videoId: String?)
    case decodingFailed(payload: String)
    case missingStreamResult

    var errorDescription: String? {
        switch self {
        case .invalidBaseURL(let value):
            return "Invalid backend URL: \(value)"
        case .invalidHTTPResponse:
            return "Invalid response from server."
        case .backendError(let code, let message, _):
            switch code {
            case "INVALID_YOUTUBE_URL":
                return "Invalid YouTube URL. Please check and try again."
            case "TRANSCRIPT_UNAVAILABLE":
                return "The video is available, but transcript is not available."
            case "TRANSCRIPT_FETCH_FAILED":
                return "Transcript provider failed. Please try again."
            case "INVALID_TRANSCRIPT":
                return "Backend returned an invalid transcript response."
            case "EMPTY_TRANSCRIPT":
                return "This video has an empty transcript."
            case "SHORT_TRANSCRIPT":
                return "This video is too short to analyze."
            case "LLM_QUOTA_OR_RATE_LIMIT":
                return "The analysis service is busy. Please try again shortly."
            case "LLM_CONTEXT_LENGTH_EXCEEDED":
                return "This video is too long to analyze."
            case "LLM_AUTH_ERROR", "LLM_PROVIDER_NOT_CONFIGURED":
                return "The analysis service isn't available right now."
            case "INVALID_CATEGORY_GRAPH":
                return "Analysis failed on the backend. Please try again."
            // LLM_* messages can carry raw provider responses, so never show them.
            case _ where code.hasPrefix("LLM_"):
                return "Analysis failed on the backend. Please try again."
            default:
                return message.isEmpty ? "Request failed with code \(code)." : message
            }
        case .serverError(let statusCode, let message):
            if message.isEmpty {
                return "Server error (\(statusCode))."
            }
            return "Server error (\(statusCode)): \(message)"
        case .decodingFailed(let payload):
            if payload.isEmpty {
                return "Could not decode server response."
            }
            return "Could not decode server response. Raw payload: \(payload)"
        case .missingStreamResult:
            return "Server finished without returning analysis data."
        }
    }
}

struct AnalyzeProgressUpdate: Decodable, Equatable, Sendable {
    let stage: String
    let message: String
}

private struct AnalyzeStreamErrorResponse: Decodable {
    let stage: String
    let statusCode: Int
    let code: String
    let message: String
}

struct URLSessionAnalyzeService: AnalyzeService {
    private let baseURL: URL
    private let session: URLSession

    init(config: AppConfig = .default, session: URLSession = .shared) throws {
        guard let baseURL = URL(string: config.backendBaseURL) else {
            throw AnalyzeServiceError.invalidBaseURL(config.backendBaseURL)
        }
        self.baseURL = baseURL
        self.session = session
    }

    func analyzeYouTube(
        title: String,
        youtubeUrl: String,
        onProgress: @escaping @Sendable (AnalyzeProgressUpdate) -> Void
    ) async throws -> AnalyzeResponse {
        var components = URLComponents(url: baseURL.appendingPathComponent("analyze"), resolvingAgainstBaseURL: false)
        components?.queryItems = [URLQueryItem(name: "stream", value: "progress")]
        guard let endpoint = components?.url else {
            throw AnalyzeServiceError.invalidBaseURL(baseURL.absoluteString)
        }

        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("text/event-stream", forHTTPHeaderField: "Accept")

        let payload = AnalyzeRequest(title: title, youtubeUrl: youtubeUrl)
        request.httpBody = try JSONEncoder().encode(payload)

        let (bytes, response) = try await session.bytes(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw AnalyzeServiceError.invalidHTTPResponse
        }

        guard (200...299).contains(httpResponse.statusCode) else {
            let data = try await collectData(from: bytes)
            if let backendError = decodeBackendError(from: data) {
                throw AnalyzeServiceError.backendError(
                    code: backendError.code,
                    message: backendError.message,
                    videoId: backendError.videoId
                )
            } else {
                let bodyMessage = String(data: data, encoding: .utf8) ?? ""
                throw AnalyzeServiceError.serverError(statusCode: httpResponse.statusCode, message: bodyMessage)
            }
        }

        var currentEvent = "message"
        var result: AnalyzeResponse?

        // bytes.lines never yields the blank line that ends an SSE event, so dispatch on
        // the data line instead. The backend writes exactly one data line per event.
        for try await rawLine in bytes.lines {
            let line = String(rawLine)

            if line.hasPrefix("event:") {
                currentEvent = String(line.dropFirst("event:".count)).trimmingCharacters(in: .whitespaces)
            } else if line.hasPrefix("data:") {
                try handleStreamEvent(
                    event: currentEvent,
                    payload: String(line.dropFirst("data:".count)).trimmingCharacters(in: .whitespaces),
                    onProgress: onProgress,
                    result: &result
                )
                currentEvent = "message"
            }
        }

        guard let result else {
            throw AnalyzeServiceError.missingStreamResult
        }

        return result
    }

    private func collectData(from bytes: URLSession.AsyncBytes) async throws -> Data {
        var data = Data()
        for try await byte in bytes {
            data.append(byte)
        }
        return data
    }

    private func handleStreamEvent(
        event: String,
        payload: String,
        onProgress: @escaping @Sendable (AnalyzeProgressUpdate) -> Void,
        result: inout AnalyzeResponse?
    ) throws {
        let payloadData = Data(payload.utf8)

        switch event {
        case "started", "progress", "completed":
            if let update = try? JSONDecoder().decode(AnalyzeProgressUpdate.self, from: payloadData) {
                onProgress(update)
            }
        case "result":
            result = try decode(AnalyzeResponse.self, from: payloadData)
        case "error":
            let error = try decode(AnalyzeStreamErrorResponse.self, from: payloadData)
            throw AnalyzeServiceError.backendError(code: error.code, message: error.message, videoId: nil)
        default:
            break
        }
    }

    private func decode<T: Decodable>(_ type: T.Type, from data: Data) throws -> T {
        do {
            return try JSONDecoder().decode(T.self, from: data)
        } catch {
            let rawPayload = String(data: data, encoding: .utf8) ?? ""
            logDecodingFailure(rawPayload)
            throw AnalyzeServiceError.decodingFailed(payload: rawPayload)
        }
    }

    private func decodeBackendError(from data: Data) -> AnalyzeErrorResponse? {
        (try? JSONDecoder().decode(AnalyzeErrorEnvelope.self, from: data))?.error
    }

    private func logDecodingFailure(_ payload: String) {
        #if DEBUG
        print("AnalyzeService decode failure payload: \(payload)")
        #endif
    }
}
