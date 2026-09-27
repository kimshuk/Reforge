import XCTest
@testable import NoteApp

@MainActor
final class PendingNoteRouterTests: XCTestCase {
    func testAppliesLatestNoteBeforeAcknowledgingCapturedRoutes() throws {
        let note = makeStoredNote()
        let routeIDs = [UUID(), UUID()]
        let store = RoutingStoreStub(
            snapshot: PendingRouteSnapshot(routeIDs: routeIDs, note: note)
        )
        var applied: StoredContentNote?

        try PendingNoteRouter(repository: store).consumeLatest {
            store.events.append("apply")
            applied = $0
        }

        XCTAssertEqual(applied, note)
        XCTAssertEqual(store.acknowledged, routeIDs)
        XCTAssertEqual(store.events, ["apply", "ack"])
    }

    func testApplyFailureKeepsRoutesAndMissingNoteAcknowledgesOrphans() throws {
        let note = makeStoredNote()
        let routeIDs = [UUID()]
        let failing = RoutingStoreStub(snapshot: .init(routeIDs: routeIDs, note: note))
        XCTAssertThrowsError(
            try PendingNoteRouter(repository: failing).consumeLatest { _ in
                failing.events.append("apply")
                throw RouterTestFailure.failed
            }
        )
        XCTAssertTrue(failing.acknowledged.isEmpty)

        let orphan = RoutingStoreStub(snapshot: .init(routeIDs: routeIDs, note: nil))
        try PendingNoteRouter(repository: orphan).consumeLatest { _ in
            XCTFail("Missing note must not be applied")
        }
        XCTAssertEqual(orphan.acknowledged, routeIDs)
    }

    private func makeStoredNote() -> StoredContentNote {
        StoredContentNote(
            id: UUID(), sourceKey: "youtube:dQw4w9WgXcQ", sourceType: "youtube",
            videoId: "dQw4w9WgXcQ", sourceURL: URL(string: "https://youtu.be/dQw4w9WgXcQ")!,
            canonicalURL: URL(string: "https://www.youtube.com/watch?v=dQw4w9WgXcQ")!,
            title: "Title", transcriptId: "id", transcriptText: "text",
            transcriptLanguageCode: "en", transcriptIsGenerated: false, createdAt: Date()
        )
    }
}

private enum RouterTestFailure: Error { case failed }

@MainActor
private final class RoutingStoreStub: PendingNoteRoutingStore {
    let snapshot: PendingRouteSnapshot
    var acknowledged: [UUID] = []
    var events: [String] = []

    init(snapshot: PendingRouteSnapshot) { self.snapshot = snapshot }
    func pendingRouteSnapshot() throws -> PendingRouteSnapshot { snapshot }
    func acknowledge(routeIDs: [UUID]) throws { acknowledged = routeIDs; events.append("ack") }
}
