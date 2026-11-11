import Foundation
import XCTest
@testable import NoteApp

@MainActor
final class AnalyzeServiceStreamTests: XCTestCase {
    override func tearDown() {
        StreamStubURLProtocol.body = ""
        super.tearDown()
    }

    func testDeliversEachProgressEventBeforeTheResult() async throws {
        StreamStubURLProtocol.body = [
            Self.event("started", #"{"stage":"started","message":"Accepted analyze request"}"#),
            Self.event("progress", #"{"stage":"chunking_topics","message":"Identifying topic chunks"}"#),
            Self.event("completed", #"{"stage":"completed","message":"Analysis complete"}"#),
            Self.event(
                "result",
                #"{"transcriptId":"t1","sourceType":"youtube","categories":[],"expiresInSeconds":1800}"#
            ),
        ].joined()
        let stages = StageRecorder()

        let result = try await makeService().analyzeYouTube(
            title: "Title",
            youtubeUrl: "https://youtu.be/dQw4w9WgXcQ"
        ) { update in
            stages.append(update.stage)
        }

        XCTAssertEqual(stages.values, ["started", "chunking_topics", "completed"])
        XCTAssertEqual(result.transcriptId, "t1")
    }

    func testMidStreamErrorEventThrowsBackendError() async throws {
        StreamStubURLProtocol.body = [
            Self.event("started", #"{"stage":"started","message":"Accepted analyze request"}"#),
            Self.event("progress", #"{"stage":"fetching_transcript","message":"Fetching YouTube transcript"}"#),
            Self.event(
                "error",
                #"{"stage":"error","statusCode":502,"code":"TRANSCRIPT_UNAVAILABLE","message":"Transcript unavailable for this video"}"#
            ),
        ].joined()

        do {
            _ = try await makeService().analyzeYouTube(
                title: "Title",
                youtubeUrl: "https://youtu.be/dQw4w9WgXcQ"
            ) { _ in }
            XCTFail("Expected backend error")
        } catch AnalyzeServiceError.backendError(let code, let message, _) {
            XCTAssertEqual(code, "TRANSCRIPT_UNAVAILABLE")
            XCTAssertEqual(message, "Transcript unavailable for this video")
        }
    }

    private func makeService() throws -> URLSessionAnalyzeService {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [StreamStubURLProtocol.self]
        return try URLSessionAnalyzeService(
            config: AppConfig(backendBaseURL: "https://api.example.com"),
            session: URLSession(configuration: configuration)
        )
    }

    // Same framing the backend writes: one event line, one data line, one blank line.
    private static func event(_ name: String, _ data: String) -> String {
        "event: \(name)\ndata: \(data)\n\n"
    }
}

private final class StageRecorder: @unchecked Sendable {
    private let lock = NSLock()
    private var stages: [String] = []

    var values: [String] {
        lock.withLock { stages }
    }

    func append(_ stage: String) {
        lock.withLock { stages.append(stage) }
    }
}

private final class StreamStubURLProtocol: URLProtocol {
    static var body = ""

    override class func canInit(with request: URLRequest) -> Bool { true }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        let response = HTTPURLResponse(
            url: request.url!,
            statusCode: 200,
            httpVersion: nil,
            headerFields: ["Content-Type": "text/event-stream"]
        )!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data(Self.body.utf8))
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}
