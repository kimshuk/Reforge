import XCTest
@testable import NoteApp

@MainActor
final class ShareExtensionViewModelTests: XCTestCase {
    func testSavedAndDuplicatePublishExactTextThenComplete() async {
        for (result, text) in [
            (ShareIngestionResult.saved(noteID: UUID()), "Saved to Reforge"),
            (.alreadySaved(noteID: UUID()), "Already saved"),
        ] {
            var completed = 0
            var cancelled = 0
            let viewModel = ShareExtensionViewModel(
                ingestor: IngestorStub(result: result),
                complete: { completed += 1 },
                cancel: { cancelled += 1 }
            )

            await viewModel.run(input: validInput)

            XCTAssertEqual(viewModel.statusText, text)
            XCTAssertFalse(viewModel.isLoading)
            XCTAssertEqual(completed, 1)
            XCTAssertEqual(cancelled, 0)
        }
    }

    func testApprovedTranscriptErrorsStayVisibleWithoutCompleting() async {
        for (code, text) in [
            ("TRANSCRIPT_UNAVAILABLE", "The video is available, but transcript is not available."),
            ("TRANSCRIPT_FETCH_FAILED", "Transcript provider failed. Please try again."),
        ] {
            var completed = 0
            var cancelled = 0
            let error = YouTubeTranscriptServiceError.backend(
                statusCode: 502,
                code: code,
                message: "backend"
            )
            let viewModel = ShareExtensionViewModel(
                ingestor: IngestorStub(error: error),
                complete: { completed += 1 },
                cancel: { cancelled += 1 }
            )

            await viewModel.run(input: validInput)

            XCTAssertEqual(viewModel.statusText, text)
            XCTAssertEqual(completed, 0)
            XCTAssertEqual(cancelled, 0)
        }
    }

    func testUnknownFailureCancelsWithoutSuccessText() async {
        var cancelled = 0
        let viewModel = ShareExtensionViewModel(
            ingestor: IngestorStub(error: TestError.failure),
            complete: {},
            cancel: { cancelled += 1 }
        )

        await viewModel.run(input: validInput)

        XCTAssertNil(viewModel.statusText)
        XCTAssertFalse(viewModel.isLoading)
        XCTAssertEqual(cancelled, 1)
    }

    func testOfflineAndTimeoutShowApprovedProviderFailureText() async {
        for code in [URLError.notConnectedToInternet, .timedOut] {
            var completed = 0
            var cancelled = 0
            let viewModel = ShareExtensionViewModel(
                ingestor: IngestorStub(error: URLError(code)),
                complete: { completed += 1 },
                cancel: { cancelled += 1 }
            )

            await viewModel.run(input: validInput)

            XCTAssertEqual(viewModel.statusText, "Transcript provider failed. Please try again.")
            XCTAssertEqual(completed, 0)
            XCTAssertEqual(cancelled, 0)
        }
    }

    private var validInput: SharedURLInput {
        SharedURLInput(
            url: URL(string: "https://youtu.be/dQw4w9WgXcQ")!,
            sharedTitle: nil
        )
    }
}

@MainActor
private struct IngestorStub: ShareIngesting {
    let result: Result<ShareIngestionResult, Error>

    init(result: ShareIngestionResult) { self.result = .success(result) }
    init(error: Error) { result = .failure(error) }

    func ingest(_ input: SharedURLInput) async throws -> ShareIngestionResult {
        try result.get()
    }
}

private enum TestError: Error { case failure }
