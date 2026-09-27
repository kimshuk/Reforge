import XCTest
@testable import NoteApp

@MainActor
final class HomeViewModelTests: XCTestCase {
    func testApplySharedNoteResetsPreviousStateWithoutAnalyzing() {
        let analyze = ControlledAnalyzeService()
        let viewModel = HomeViewModel(
            analyzeService: analyze,
            youtubeTitleService: StaticTitleService()
        )
        viewModel.youtubeLink = "https://youtu.be/aaaaaaaaaaa"
        viewModel.titleInput = "Old"
        viewModel.isLoading = true
        viewModel.loadingStage = "working"
        viewModel.loadingStatusMessage = "Working"
        viewModel.errorMessage = "Old error"
        viewModel.videoUnavailableReason = .unknown
        let before = viewModel.inputGeneration

        viewModel.applySharedNote(makeStoredNote())

        XCTAssertEqual(viewModel.youtubeLink, "https://youtu.be/dQw4w9WgXcQ")
        XCTAssertEqual(viewModel.titleInput, "Shared title")
        XCTAssertFalse(viewModel.isLoading)
        XCTAssertEqual(viewModel.loadingStage, "")
        XCTAssertEqual(viewModel.loadingStatusMessage, "")
        XCTAssertEqual(viewModel.errorMessage, "")
        XCTAssertNil(viewModel.analysisResult)
        XCTAssertNil(viewModel.videoUnavailableReason)
        XCTAssertEqual(viewModel.inputGeneration, before + 1)
        XCTAssertEqual(analyze.callCount, 0)
    }

    func testLateProgressAndErrorCannotReplaceSharedNote() async throws {
        let analyze = ControlledAnalyzeService()
        let viewModel = HomeViewModel(
            analyzeService: analyze,
            youtubeTitleService: StaticTitleService()
        )
        viewModel.youtubeLink = "https://youtu.be/aaaaaaaaaaa"
        viewModel.titleInput = "Old"
        let task = Task { await viewModel.analyze() }
        await analyze.waitUntilStarted()

        viewModel.applySharedNote(makeStoredNote())
        analyze.sendProgress(.init(stage: "late", message: "Late"))
        analyze.resume(throwing: TestFailure.failed)
        await task.value

        XCTAssertEqual(viewModel.youtubeLink, "https://youtu.be/dQw4w9WgXcQ")
        XCTAssertEqual(viewModel.titleInput, "Shared title")
        XCTAssertFalse(viewModel.isLoading)
        XCTAssertEqual(viewModel.loadingStage, "")
        XCTAssertEqual(viewModel.errorMessage, "")
        XCTAssertNil(viewModel.analysisResult)
    }

    private func makeStoredNote() -> StoredContentNote {
        StoredContentNote(
            id: UUID(), sourceKey: "youtube:dQw4w9WgXcQ", sourceType: "youtube",
            videoId: "dQw4w9WgXcQ", sourceURL: URL(string: "https://youtu.be/dQw4w9WgXcQ")!,
            canonicalURL: URL(string: "https://www.youtube.com/watch?v=dQw4w9WgXcQ")!,
            title: "Shared title", transcriptId: "id", transcriptText: "text",
            transcriptLanguageCode: "en", transcriptIsGenerated: false, createdAt: Date()
        )
    }
}

@MainActor
private final class ControlledAnalyzeService: AnalyzeService {
    private var continuation: CheckedContinuation<AnalyzeResponse, Error>?
    private var startedContinuation: CheckedContinuation<Void, Never>?
    private var progress: (@Sendable (AnalyzeProgressUpdate) -> Void)?
    private(set) var callCount = 0

    func analyzeYouTube(title: String, youtubeUrl: String, onProgress: @escaping @Sendable (AnalyzeProgressUpdate) -> Void) async throws -> AnalyzeResponse {
        callCount += 1
        progress = onProgress
        startedContinuation?.resume()
        startedContinuation = nil
        return try await withCheckedThrowingContinuation { continuation = $0 }
    }

    func waitUntilStarted() async {
        if callCount > 0 { return }
        await withCheckedContinuation { startedContinuation = $0 }
    }

    func sendProgress(_ update: AnalyzeProgressUpdate) { progress?(update) }
    func resume(throwing error: Error) { continuation?.resume(throwing: error); continuation = nil }
}

private struct StaticTitleService: YouTubeTitleService {
    func checkAvailability(for youtubeURL: String) async throws -> YouTubeAvailabilityResult {
        .available(title: "Late title")
    }
}

private enum TestFailure: Error { case failed }
