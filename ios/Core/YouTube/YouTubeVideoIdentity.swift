import Foundation

enum YouTubeVideoIdentityError: Error {
    case invalidYouTubeURL
}

struct YouTubeVideoIdentity: Equatable {
    let videoID: String
    let canonicalURL: URL
    let sourceKey: String

    init(url: URL) throws {
        guard
            let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
            let scheme = components.scheme?.lowercased(),
            scheme == "http" || scheme == "https",
            var host = components.host?.lowercased()
        else {
            throw YouTubeVideoIdentityError.invalidYouTubeURL
        }

        if host.hasPrefix("www.") {
            host.removeFirst(4)
        }

        let candidate: String?
        if host == "youtu.be" {
            candidate = components.path.split(separator: "/").first.map(String.init)
        } else if host == "youtube.com" || host == "m.youtube.com" {
            if components.path == "/watch" {
                candidate = components.queryItems?.first(where: { $0.name == "v" })?.value
            } else {
                let pathParts = components.path.split(separator: "/")
                candidate = pathParts.count == 2 && pathParts[0] == "shorts"
                    ? String(pathParts[1])
                    : nil
            }
        } else {
            candidate = nil
        }

        guard
            let candidate,
            candidate.range(of: #"^[A-Za-z0-9_-]{11}$"#, options: .regularExpression) != nil,
            let canonicalURL = URL(
                string: "https://www.youtube.com/watch?v=\(candidate)"
            )
        else {
            throw YouTubeVideoIdentityError.invalidYouTubeURL
        }

        videoID = candidate
        self.canonicalURL = canonicalURL
        sourceKey = "youtube:\(candidate)"
    }
}
