import Foundation
import XCTest
@testable import NoteApp

@MainActor
final class YouTubeVideoIdentityTests: XCTestCase {
    func testSupportedURLsConvergeOnCanonicalIdentity() throws {
        let urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&feature=shared",
            "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ?t=42",
            "https://youtube.com/shorts/dQw4w9WgXcQ?feature=share",
        ]

        for value in urls {
            let identity = try YouTubeVideoIdentity(url: try XCTUnwrap(URL(string: value)))

            XCTAssertEqual(identity.videoID, "dQw4w9WgXcQ")
            XCTAssertEqual(
                identity.canonicalURL.absoluteString,
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            )
            XCTAssertEqual(identity.sourceKey, "youtube:dQw4w9WgXcQ")
        }
    }

    func testRejectsUnsupportedOrMalformedURLs() throws {
        XCTAssertNil(URL(string: ""))
        let values = [
            "javascript://youtube.com/watch?v=dQw4w9WgXcQ",
            "https://example.com/watch?v=dQw4w9WgXcQ",
            "https://youtube.com/embed/dQw4w9WgXcQ",
            "https://youtube.com/watch?v=dQw4w9WgXC",
            "https://youtube.com/watch?v=dQw4w9WgXcQQ",
        ]

        for value in values {
            let url = try XCTUnwrap(URL(string: value))
            XCTAssertThrowsError(try YouTubeVideoIdentity(url: url), value)
        }
    }
}
