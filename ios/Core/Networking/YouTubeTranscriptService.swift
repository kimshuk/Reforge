import Foundation

struct YouTubeTranscriptRequest: Encodable, Equatable {
    let youtubeUrl: String
    let title: String?
}

struct YouTubeTranscriptResponse: Decodable, Equatable {
    let transcriptId: String
    let videoId: String
    let canonicalYoutubeUrl: URL
    let transcriptText: String
    let languageCode: String?
    let language: String?
    let isGenerated: Bool?
}

enum YouTubeTranscriptServiceError: Error, Equatable {
    case backend(statusCode: Int, code: String, message: String)
    case invalidResponse(statusCode: Int)
    case videoIdentityMismatch
}

protocol YouTubeTranscriptFetching {
    func fetch(youtubeURL: URL, title: String?) async throws -> YouTubeTranscriptResponse
}

struct URLSessionYouTubeTranscriptService: YouTubeTranscriptFetching {
    private let baseURL: URL
    private let session: URLSession
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()

    init(baseURL: URL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
    }

    func fetch(youtubeURL: URL, title: String?) async throws -> YouTubeTranscriptResponse {
        let identity = try YouTubeVideoIdentity(url: youtubeURL)
        let endpoint = baseURL.appendingPathComponent("youtube/transcript")
        var request = URLRequest(url: endpoint, timeoutInterval: 30)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoder.encode(
            YouTubeTranscriptRequest(
                youtubeUrl: identity.canonicalURL.absoluteString,
                title: title
            )
        )

        let (data, rawResponse) = try await session.data(for: request)
        guard let response = rawResponse as? HTTPURLResponse else {
            throw YouTubeTranscriptServiceError.invalidResponse(statusCode: 0)
        }
        guard (200..<300).contains(response.statusCode) else {
            let envelope = try? decoder.decode(BackendErrorEnvelope.self, from: data)
            if let error = envelope?.error {
                throw YouTubeTranscriptServiceError.backend(
                    statusCode: response.statusCode,
                    code: error.code,
                    message: error.message
                )
            }
            throw YouTubeTranscriptServiceError.invalidResponse(
                statusCode: response.statusCode
            )
        }

        let result = try decoder.decode(YouTubeTranscriptResponse.self, from: data)
        guard result.videoId == identity.videoID else {
            throw YouTubeTranscriptServiceError.videoIdentityMismatch
        }
        return result
    }
}

private struct BackendErrorEnvelope: Decodable {
    let error: BackendErrorPayload
}

private struct BackendErrorPayload: Decodable {
    let code: String
    let message: String
}
