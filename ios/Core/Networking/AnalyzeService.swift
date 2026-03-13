import Foundation

struct AnalyzeErrorResponse: Decodable {
    let code: String
    let message: String
    let videoId: String?
    let details: [String: JSONValue]?
}

enum JSONValue: Decodable {
    case string(String)
    case number(Double)
    case bool(Bool)
    case object([String: JSONValue])
    case array([JSONValue])
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let value = try? container.decode(String.self) {
            self = .string(value)
        } else if let value = try? container.decode(Double.self) {
            self = .number(value)
        } else if let value = try? container.decode(Bool.self) {
            self = .bool(value)
        } else if let value = try? container.decode([String: JSONValue].self) {
            self = .object(value)
        } else if let value = try? container.decode([JSONValue].self) {
            self = .array(value)
        } else {
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Invalid JSON value.")
        }
    }
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
    case decodingFailed
    case missingStreamResult

    var errorDescription: String? {
        switch self {
        case .invalidBaseURL(let value):
            return "Invalid backend URL: \(value)"
        case .invalidHTTPResponse:
            return "Invalid response from server."
        case .backendError(let code, let message, _):
            switch code {
            case "YOUTUBE_VIDEO_UNAVAILABLE":
                return "This YouTube video is unavailable (private, hidden, or removed)."
            case "YOUTUBE_URL_INVALID":
                return "Invalid YouTube URL. Please check and try again."
            case "TRANSCRIPT_UNAVAILABLE":
                return "The video is available, but transcript is not available."
            case "TRANSCRIPT_PROVIDER_RATE_LIMITED":
                return "Transcript provider is rate-limiting requests. Please try again."
            case "TRANSCRIPT_PROVIDER_ERROR":
                return "Transcript provider failed. Please try again."
            default:
                return message.isEmpty ? "Request failed with code \(code)." : message
            }
        case .serverError(let statusCode, let message):
            if message.isEmpty {
                return "Server error (\(statusCode))."
            }
            return "Server error (\(statusCode)): \(message)"
        case .decodingFailed:
            return "Could not decode server response."
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
            if let backendError = try? JSONDecoder().decode(AnalyzeErrorResponse.self, from: data) {
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

        let contentType = httpResponse.value(forHTTPHeaderField: "Content-Type")?.lowercased() ?? ""
        if !contentType.contains("text/event-stream") {
            let data = try await collectData(from: bytes)
            if let response = tryDecodeAnalyzeResponse(from: data) {
                return response
            }

            let rawBody = String(data: data, encoding: .utf8) ?? ""
            throw AnalyzeServiceError.serverError(
                statusCode: httpResponse.statusCode,
                message: rawBody.isEmpty ? "Could not decode server response." : rawBody
            )
        }

        var currentEvent = "message"
        var currentDataLines: [String] = []
        var result: AnalyzeResponse?

        for try await rawLine in bytes.lines {
            let line = String(rawLine)

            if line.isEmpty {
                try handleStreamEvent(
                    event: currentEvent,
                    dataLines: currentDataLines,
                    onProgress: onProgress,
                    result: &result
                )
                currentEvent = "message"
                currentDataLines.removeAll(keepingCapacity: true)
                continue
            }

            if line.hasPrefix("event:") {
                currentEvent = String(line.dropFirst("event:".count)).trimmingCharacters(in: .whitespaces)
            } else if line.hasPrefix("data:") {
                currentDataLines.append(
                    String(line.dropFirst("data:".count)).trimmingCharacters(in: .whitespaces)
                )
            }
        }

        try handleStreamEvent(
            event: currentEvent,
            dataLines: currentDataLines,
            onProgress: onProgress,
            result: &result
        )

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
        dataLines: [String],
        onProgress: @escaping @Sendable (AnalyzeProgressUpdate) -> Void,
        result: inout AnalyzeResponse?
    ) throws {
        guard !dataLines.isEmpty else { return }
        let payload = dataLines.joined(separator: "\n")
        let payloadData = Data(payload.utf8)

        switch event {
        case "started", "progress", "completed":
            if let update = try? JSONDecoder().decode(AnalyzeProgressUpdate.self, from: payloadData) {
                onProgress(update)
            }
        case "result":
            if let decoded = tryDecodeAnalyzeResponse(from: payloadData) {
                result = decoded
            } else if let wrapped = try? JSONSerialization.jsonObject(with: payloadData) as? [String: Any],
                      let nested = wrapped["data"] ?? wrapped["result"],
                      JSONSerialization.isValidJSONObject(nested) {
                let nestedData = try JSONSerialization.data(withJSONObject: nested)
                result = try decode(AnalyzeResponse.self, from: nestedData)
            } else {
                throw AnalyzeServiceError.serverError(
                    statusCode: 200,
                    message: String(data: payloadData, encoding: .utf8) ?? "Could not decode server response."
                )
            }
        case "error":
            let error = try decode(AnalyzeStreamErrorResponse.self, from: payloadData)
            throw AnalyzeServiceError.backendError(code: error.code, message: error.message, videoId: nil)
        default:
            break
        }
    }

    private func tryDecodeAnalyzeResponse(from data: Data) -> AnalyzeResponse? {
        if let decoded = try? JSONDecoder().decode(AnalyzeResponse.self, from: data) {
            return decoded
        }

        if let wrapped = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let nested = wrapped["data"] ?? wrapped["result"],
           JSONSerialization.isValidJSONObject(nested),
           let nestedData = try? JSONSerialization.data(withJSONObject: nested),
           let decoded = try? JSONDecoder().decode(AnalyzeResponse.self, from: nestedData) {
            return decoded
        }

        guard let text = String(data: data, encoding: .utf8) else {
            return nil
        }

        for objectData in extractConcatenatedJsonObjects(from: text).reversed() {
            if let decoded = try? JSONDecoder().decode(AnalyzeResponse.self, from: objectData) {
                return decoded
            }

            if let wrapped = try? JSONSerialization.jsonObject(with: objectData) as? [String: Any],
               let nested = wrapped["data"] ?? wrapped["result"],
               JSONSerialization.isValidJSONObject(nested),
               let nestedData = try? JSONSerialization.data(withJSONObject: nested),
               let decoded = try? JSONDecoder().decode(AnalyzeResponse.self, from: nestedData) {
                return decoded
            }
        }

        return nil
    }

    private func extractConcatenatedJsonObjects(from text: String) -> [Data] {
        var objects: [Data] = []
        var braceDepth = 0
        var startIndex: String.Index?
        var isInsideString = false
        var isEscaping = false

        for index in text.indices {
            let character = text[index]

            if isInsideString {
                if isEscaping {
                    isEscaping = false
                } else if character == "\\" {
                    isEscaping = true
                } else if character == "\"" {
                    isInsideString = false
                }
                continue
            }

            if character == "\"" {
                isInsideString = true
                continue
            }

            if character == "{" {
                if braceDepth == 0 {
                    startIndex = index
                }
                braceDepth += 1
            } else if character == "}" {
                guard braceDepth > 0 else { continue }
                braceDepth -= 1

                if braceDepth == 0, let objectStartIndex = startIndex {
                    let endIndex = text.index(after: index)
                    let candidate = text[objectStartIndex..<endIndex]
                    if let data = String(candidate).data(using: .utf8) {
                        objects.append(data)
                    }
                    startIndex = nil
                }
            }
        }

        return objects
    }

    private func decode<T: Decodable>(_ type: T.Type, from data: Data) throws -> T {
        do {
            return try JSONDecoder().decode(T.self, from: data)
        } catch {
            throw AnalyzeServiceError.decodingFailed
        }
    }
}
