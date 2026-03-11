import Foundation

enum VideoUnavailableReason: Equatable {
    case privateOrRestricted
    case notFoundOrRemoved
    case rateLimited
    case unknown

    var userMessage: String {
        switch self {
        case .privateOrRestricted:
            return "This video is private or restricted."
        case .notFoundOrRemoved:
            return "This video was removed or is not found."
        case .rateLimited:
            return "YouTube is rate-limiting checks right now. Please try again."
        case .unknown:
            return "Unable to verify YouTube video availability."
        }
    }
}

enum YouTubeAvailabilityResult: Equatable {
    case available(title: String)
    case unavailable(reason: VideoUnavailableReason)
}

protocol YouTubeTitleService {
    func checkAvailability(for youtubeURL: String) async throws -> YouTubeAvailabilityResult
}

enum YouTubeTitleServiceError: Error {
    case invalidURL
    case requestFailed
    case decodingFailed
}

private struct YouTubeOEmbedResponse: Codable {
    let title: String
}

struct YouTubeOEmbedService: YouTubeTitleService {
    private let session: URLSession

    init(session: URLSession = .shared) {
        self.session = session
    }

    func checkAvailability(for youtubeURL: String) async throws -> YouTubeAvailabilityResult {
        guard let escapedURL = youtubeURL.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed),
              let oEmbedURL = URL(string: "https://www.youtube.com/oembed?url=\(escapedURL)&format=json") else {
            throw YouTubeTitleServiceError.invalidURL
        }

        let (data, response) = try await session.data(from: oEmbedURL)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw YouTubeTitleServiceError.requestFailed
        }

        switch httpResponse.statusCode {
        case 200...299:
            break
        case 401:
            return .unavailable(reason: .privateOrRestricted)
        case 404:
            return .unavailable(reason: .notFoundOrRemoved)
        case 429:
            return .unavailable(reason: .rateLimited)
        default:
            return .unavailable(reason: .unknown)
        }

        do {
            let payload = try JSONDecoder().decode(YouTubeOEmbedResponse.self, from: data)
            return .available(title: payload.title)
        } catch {
            throw YouTubeTitleServiceError.decodingFailed
        }
    }
}
