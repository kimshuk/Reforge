import Foundation
import XCTest
@testable import NoteApp

@MainActor
final class YouTubeTranscriptServiceTests: XCTestCase {
    override func tearDown() {
        StubURLProtocol.requestHandler = nil
        super.tearDown()
    }

    func testPostsCanonicalRequestWithThirtySecondTimeoutAndDecodesResponse() async throws {
        StubURLProtocol.requestHandler = { request in
            XCTAssertEqual(request.httpMethod, "POST")
            XCTAssertEqual(request.url?.path, "/v1/youtube/transcript")
            XCTAssertEqual(request.timeoutInterval, 30, accuracy: 0.001)
            XCTAssertEqual(request.value(forHTTPHeaderField: "Content-Type"), "application/json")

            let body = try Self.bodyData(from: request)
            let json = try XCTUnwrap(
                JSONSerialization.jsonObject(with: body) as? [String: String]
            )
            XCTAssertEqual(
                json,
                [
                    "youtubeUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    "title": "Shared title",
                ]
            )
            return Self.response(
                request: request,
                statusCode: 200,
                body: Self.successBody
            )
        }

        let result = try await makeService().fetch(
            youtubeURL: try XCTUnwrap(URL(string: "https://youtu.be/dQw4w9WgXcQ?t=42")),
            title: "Shared title"
        )

        XCTAssertEqual(result.transcriptId, "11111111-1111-4111-8111-111111111111")
        XCTAssertEqual(result.videoId, "dQw4w9WgXcQ")
        XCTAssertEqual(
            result.canonicalYoutubeUrl.absoluteString,
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )
        XCTAssertEqual(result.transcriptText, "Transcript text")
        XCTAssertEqual(result.languageCode, "en")
        XCTAssertEqual(result.language, "English")
        XCTAssertEqual(result.isGenerated, false)
    }

    func testDecodesBackendErrorEnvelope() async throws {
        StubURLProtocol.requestHandler = { request in
            Self.response(
                request: request,
                statusCode: 502,
                body: #"{"error":{"code":"TRANSCRIPT_UNAVAILABLE","message":"No transcript"}}"#
            )
        }

        do {
            _ = try await makeService().fetch(
                youtubeURL: try XCTUnwrap(URL(string: "https://youtu.be/dQw4w9WgXcQ")),
                title: nil
            )
            XCTFail("Expected backend error")
        } catch let error as YouTubeTranscriptServiceError {
            XCTAssertEqual(
                error,
                .backend(
                    statusCode: 502,
                    code: "TRANSCRIPT_UNAVAILABLE",
                    message: "No transcript"
                )
            )
        }
    }

    func testDecodesUnknownGeneratedStatusAsNil() async throws {
        StubURLProtocol.requestHandler = { request in
            Self.response(
                request: request,
                statusCode: 200,
                body: Self.successBody.replacingOccurrences(
                    of: "\"isGenerated\":false",
                    with: "\"isGenerated\":null"
                )
            )
        }

        let result = try await makeService().fetch(
            youtubeURL: try XCTUnwrap(URL(string: "https://youtu.be/dQw4w9WgXcQ")),
            title: nil
        )

        XCTAssertNil(result.isGenerated)
    }

    func testRejectsResponseForDifferentVideo() async throws {
        StubURLProtocol.requestHandler = { request in
            Self.response(
                request: request,
                statusCode: 200,
                body: Self.successBody.replacingOccurrences(
                    of: "dQw4w9WgXcQ",
                    with: "aaaaaaaaaaa"
                )
            )
        }

        do {
            _ = try await makeService().fetch(
                youtubeURL: try XCTUnwrap(URL(string: "https://youtu.be/dQw4w9WgXcQ")),
                title: nil
            )
            XCTFail("Expected video identity mismatch")
        } catch let error as YouTubeTranscriptServiceError {
            XCTAssertEqual(error, .videoIdentityMismatch)
        }
    }

    private func makeService() -> URLSessionYouTubeTranscriptService {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [StubURLProtocol.self]
        return URLSessionYouTubeTranscriptService(
            baseURL: URL(string: "https://api.example.com/v1/")!,
            session: URLSession(configuration: configuration)
        )
    }

    private static func response(
        request: URLRequest,
        statusCode: Int,
        body: String
    ) -> (HTTPURLResponse, Data) {
        let response = HTTPURLResponse(
            url: request.url!,
            statusCode: statusCode,
            httpVersion: nil,
            headerFields: ["Content-Type": "application/json"]
        )!
        return (response, Data(body.utf8))
    }

    private static func bodyData(from request: URLRequest) throws -> Data {
        if let body = request.httpBody {
            return body
        }
        let stream = try XCTUnwrap(request.httpBodyStream)
        stream.open()
        defer { stream.close() }

        var data = Data()
        var buffer = [UInt8](repeating: 0, count: 1_024)
        while true {
            let count = stream.read(&buffer, maxLength: buffer.count)
            if count < 0 {
                throw stream.streamError ?? URLError(.cannotDecodeContentData)
            }
            if count == 0 {
                return data
            }
            data.append(buffer, count: count)
        }
    }

    private static let successBody = #"""
    {
      "transcriptId":"11111111-1111-4111-8111-111111111111",
      "videoId":"dQw4w9WgXcQ",
      "canonicalYoutubeUrl":"https://www.youtube.com/watch?v=dQw4w9WgXcQ",
      "transcriptText":"Transcript text",
      "languageCode":"en",
      "language":"English",
      "isGenerated":false
    }
    """#
}

private final class StubURLProtocol: URLProtocol {
    static var requestHandler: ((URLRequest) throws -> (HTTPURLResponse, Data))?

    override class func canInit(with request: URLRequest) -> Bool { true }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        guard let handler = Self.requestHandler else {
            fatalError("StubURLProtocol.requestHandler was not set")
        }
        do {
            let (response, data) = try handler(request)
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }

    override func stopLoading() {}
}
