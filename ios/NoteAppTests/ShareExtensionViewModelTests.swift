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

    func testRestoreConfirmationUsesExactTextAndCompletesOnce() async {
        let noteID = UUID()
        var completed = 0
        var cancelled = 0
        let ingestor = IngestorStub(result: .restoreRequired(noteID: noteID))
        let viewModel = ShareExtensionViewModel(
            ingestor: ingestor,
            complete: { completed += 1 },
            cancel: { cancelled += 1 }
        )

        await viewModel.run(input: validInput)
        XCTAssertEqual(viewModel.phase, .awaitingRestore(noteID))
        XCTAssertEqual(viewModel.statusText, "This video is in Trash. Restore it?")
        XCTAssertFalse(viewModel.isLoading)
        XCTAssertEqual(completed, 0)

        await viewModel.confirmRestore()
        XCTAssertEqual(viewModel.phase, .finished)
        XCTAssertEqual(viewModel.statusText, "Already saved")
        XCTAssertEqual(completed, 1)
        XCTAssertEqual(cancelled, 0)
    }

    func testCancelPreventsLaterRestoreAndFinishesOnce() async {
        let noteID = UUID()
        var completed = 0
        var cancelled = 0
        let viewModel = ShareExtensionViewModel(
            ingestor: IngestorStub(result: .restoreRequired(noteID: noteID)),
            complete: { completed += 1 },
            cancel: { cancelled += 1 }
        )
        await viewModel.run(input: validInput)

        viewModel.cancelRestore()
        await viewModel.confirmRestore()
        viewModel.cancelRestore()

        XCTAssertEqual(viewModel.phase, .finished)
        XCTAssertEqual(completed, 0)
        XCTAssertEqual(cancelled, 1)
    }

    func testRapidRestoreTapsAndCancelIgnoreLateCompletion() async {
        let noteID = UUID()
        let ingestor = SuspendedRestoreIngestor(noteID: noteID)
        var completed = 0
        var cancelled = 0
        let viewModel = ShareExtensionViewModel(
            ingestor: ingestor,
            complete: { completed += 1 },
            cancel: { cancelled += 1 }
        )
        await viewModel.run(input: validInput)

        let first = Task { await viewModel.confirmRestore() }
        await ingestor.waitUntilStarted()
        XCTAssertEqual(viewModel.phase, .restoring(noteID))
        XCTAssertTrue(viewModel.isLoading)
        await viewModel.confirmRestore()
        XCTAssertEqual(ingestor.restoreCount, 1)
        viewModel.cancelRestore()
        ingestor.resume(returning: .alreadySaved(noteID: noteID))
        await first.value

        XCTAssertEqual(viewModel.phase, .finished)
        XCTAssertNotEqual(viewModel.statusText, "Already saved")
        XCTAssertEqual(completed, 0)
        XCTAssertEqual(cancelled, 1)
    }

    func testFailedOrExternallyCancelledRestoreNeverCompletes() async {
        for cancelTask in [false, true] {
            let noteID = UUID()
            let ingestor = SuspendedRestoreIngestor(noteID: noteID)
            var completed = 0
            var cancelled = 0
            let viewModel = ShareExtensionViewModel(
                ingestor: ingestor,
                complete: { completed += 1 },
                cancel: { cancelled += 1 }
            )
            await viewModel.run(input: validInput)
            let task = Task { await viewModel.confirmRestore() }
            await ingestor.waitUntilStarted()
            if cancelTask { task.cancel() }
            if cancelTask {
                ingestor.resume(returning: .alreadySaved(noteID: noteID))
            } else {
                ingestor.resume(throwing: TestError.failure)
            }
            await task.value

            XCTAssertEqual(viewModel.phase, .finished)
            XCTAssertNotEqual(viewModel.statusText, "Already saved")
            XCTAssertEqual(completed, 0)
            XCTAssertEqual(cancelled, 1)
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

    func restore(noteID: UUID) async throws -> ShareIngestionResult {
        .alreadySaved(noteID: noteID)
    }
}

@MainActor
private final class SuspendedRestoreIngestor: ShareIngesting {
    let noteID: UUID
    private var continuation: CheckedContinuation<ShareIngestionResult, Error>?
    private var startedContinuation: CheckedContinuation<Void, Never>?
    private(set) var restoreCount = 0

    init(noteID: UUID) { self.noteID = noteID }

    func ingest(_ input: SharedURLInput) async throws -> ShareIngestionResult {
        .restoreRequired(noteID: noteID)
    }

    func restore(noteID: UUID) async throws -> ShareIngestionResult {
        restoreCount += 1
        startedContinuation?.resume()
        startedContinuation = nil
        return try await withCheckedThrowingContinuation { continuation = $0 }
    }

    func waitUntilStarted() async {
        if restoreCount > 0 { return }
        await withCheckedContinuation { startedContinuation = $0 }
    }

    func resume(returning result: ShareIngestionResult) {
        continuation?.resume(returning: result)
        continuation = nil
    }

    func resume(throwing error: Error) {
        continuation?.resume(throwing: error)
        continuation = nil
    }
}

private enum TestError: Error { case failure }
