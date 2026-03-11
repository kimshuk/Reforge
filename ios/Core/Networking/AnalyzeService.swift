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
    func analyzeYouTube(title: String, youtubeUrl: String) async throws -> AnalyzeResponse
}

enum AnalyzeServiceError: Error, LocalizedError {
    case invalidBaseURL(String)
    case invalidHTTPResponse
    case serverError(statusCode: Int, message: String)
    case backendError(code: String, message: String, videoId: String?)
    case decodingFailed

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
        }
    }
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

    func analyzeYouTube(title: String, youtubeUrl: String) async throws -> AnalyzeResponse {
        let endpoint = baseURL.appendingPathComponent("analyze")
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let payload = AnalyzeRequest(title: title, youtubeUrl: youtubeUrl)
        request.httpBody = try JSONEncoder().encode(payload)

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw AnalyzeServiceError.invalidHTTPResponse
        }

        guard (200...299).contains(httpResponse.statusCode) else {
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

        do {
            return try JSONDecoder().decode(AnalyzeResponse.self, from: data)
        } catch {
            throw AnalyzeServiceError.decodingFailed
        }
    }
}
