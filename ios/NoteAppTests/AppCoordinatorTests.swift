import XCTest
@testable import NoteApp

@MainActor
final class AppCoordinatorTests: XCTestCase {
    func testActivationPurgesThenOpensLatestNoteInMyNotes() {
        let now = Date(timeIntervalSince1970: 4_000_000)
        let routeID = UUID()
        let noteID = UUID()
        var events: [String] = []
        let routingStore = CoordinatorRoutingStore(routeID: routeID, noteID: noteID) {
            events.append($0)
        }
        let service = CoordinatorAnalyzeService()
        let coordinator = makeCoordinator(
            service: service,
            store: routingStore,
            now: now,
            purge: { cutoff in
                XCTAssertEqual(cutoff, now.addingTimeInterval(-30 * 24 * 60 * 60))
                events.append("purge")
            }
        )

        coordinator.activate()

        XCTAssertEqual(events, ["purge", "snapshot", "ack"])
        XCTAssertEqual(coordinator.selectedTab, .myNotes)
        XCTAssertEqual(coordinator.notesPath, [.detail(noteID)])
        XCTAssertEqual(service.callCount, 0)
    }

    func testOpenNoteReplacesExistingNotesPath() {
        let coordinator = makeCoordinator()
        let noteID = UUID()
        coordinator.notesPath = [.trash, .detail(UUID())]

        coordinator.openNote(noteID)

        XCTAssertEqual(coordinator.selectedTab, .myNotes)
        XCTAssertEqual(coordinator.notesPath, [.detail(noteID)])
    }

    func testAnalyzeSelectsHomeAppliesNoteAndStartsExactlyOnce() async {
        let service = CoordinatorAnalyzeService()
        let coordinator = makeCoordinator(service: service)
        let note = makeStoredNote()
        coordinator.openNote(note.id)

        await coordinator.analyze(note)

        XCTAssertEqual(coordinator.selectedTab, .home)
        XCTAssertEqual(coordinator.homeViewModel.titleInput, note.title)
        XCTAssertEqual(coordinator.homeViewModel.youtubeLink, note.canonicalURL.absoluteString)
        XCTAssertEqual(service.callCount, 1)
        XCTAssertEqual(service.receivedURLs, [note.canonicalURL.absoluteString])
    }

    func testPurgeFailureDoesNotBlockRouteAndRetriesOnNextActivation() {
        let noteID = UUID()
        let store = CoordinatorRoutingStore(routeID: UUID(), noteID: noteID)
        var purgeAttempts = 0
        let coordinator = makeCoordinator(store: store, purge: { _ in
            purgeAttempts += 1
            if purgeAttempts == 1 { throw CoordinatorTestFailure.failed }
        })

        coordinator.activate()
        XCTAssertEqual(coordinator.notesPath, [.detail(noteID)])
        XCTAssertEqual(purgeAttempts, 1)

        coordinator.activate()
        XCTAssertEqual(purgeAttempts, 2)
    }

    private func makeCoordinator(
        service: CoordinatorAnalyzeService? = nil,
        store: CoordinatorRoutingStore? = nil,
        now: Date = Date(timeIntervalSince1970: 4_000_000),
        purge: @escaping (Date) throws -> Void = { _ in }
    ) -> AppCoordinator {
        let home = HomeViewModel(
            analyzeService: service ?? CoordinatorAnalyzeService(),
            youtubeTitleService: CoordinatorTitleService()
        )
        return AppCoordinator(
            homeViewModel: home,
            router: PendingNoteRouter(repository: store ?? CoordinatorRoutingStore()),
            purgeExpiredTrash: purge,
            now: { now }
        )
    }

    private func makeStoredNote() -> StoredContentNote {
        StoredContentNote(
            id: UUID(), sourceKey: "youtube:dQw4w9WgXcQ", sourceType: "youtube",
            videoId: "dQw4w9WgXcQ", sourceURL: URL(string: "https://youtu.be/dQw4w9WgXcQ")!,
            canonicalURL: URL(string: "https://www.youtube.com/watch?v=dQw4w9WgXcQ")!,
            title: "Saved title", transcriptId: "id", transcriptText: "text",
            transcriptLanguageCode: "en", transcriptIsGenerated: false, createdAt: Date()
        )
    }
}

private enum CoordinatorTestFailure: Error { case failed }

@MainActor
private final class CoordinatorRoutingStore: PendingNoteRoutingStore {
    private var routeID: UUID?
    private let noteID: UUID?
    private let onEvent: (String) -> Void

    init(routeID: UUID? = nil, noteID: UUID? = nil, onEvent: @escaping (String) -> Void = { _ in }) {
        self.routeID = routeID
        self.noteID = noteID
        self.onEvent = onEvent
    }

    func pendingRouteSnapshot() throws -> PendingRouteSnapshot {
        if routeID != nil { onEvent("snapshot") }
        return PendingRouteSnapshot(routeIDs: routeID.map { [$0] } ?? [], noteID: noteID)
    }

    func acknowledge(routeIDs: [UUID]) throws {
        onEvent("ack")
        if let routeID, routeIDs.contains(routeID) { self.routeID = nil }
    }
}

@MainActor
private final class CoordinatorAnalyzeService: AnalyzeService {
    private(set) var callCount = 0
    private(set) var receivedURLs: [String] = []

    func analyzeYouTube(
        title: String,
        youtubeUrl: String,
        onProgress: @escaping @Sendable (AnalyzeProgressUpdate) -> Void
    ) async throws -> AnalyzeResponse {
        callCount += 1
        receivedURLs.append(youtubeUrl)
        throw CoordinatorTestFailure.failed
    }
}

private struct CoordinatorTitleService: YouTubeTitleService {
    func checkAvailability(for youtubeURL: String) async throws -> YouTubeAvailabilityResult {
        .available(title: "Unexpected title")
    }
}
