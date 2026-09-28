import XCTest
@testable import NoteApp

@MainActor
final class PendingNoteRouterTests: XCTestCase {
    func testOpensLatestNoteBeforeAcknowledgingCapturedRoutes() throws {
        let olderRoute = UUID()
        let latestRoute = UUID()
        let noteID = UUID()
        let store = RoutingStoreStub(routes: [
            (olderRoute, UUID()), (latestRoute, noteID)
        ])
        var opened: UUID?

        try PendingNoteRouter(repository: store).consumeLatest { id in
            store.events.append("open")
            opened = id
        }

        XCTAssertEqual(opened, noteID)
        XCTAssertEqual(store.acknowledged, [[olderRoute, latestRoute]])
        XCTAssertEqual(store.events, ["open", "ack"])
    }

    func testAcknowledgeKeepsRouteCreatedAfterSnapshot() throws {
        let firstRoute = UUID()
        let latestRoute = UUID()
        let laterRoute = UUID()
        let noteID = UUID()
        let store = RoutingStoreStub(routes: [
            (firstRoute, UUID()), (latestRoute, noteID)
        ])

        try PendingNoteRouter(repository: store).consumeLatest { _ in
            store.routes.append((laterRoute, UUID()))
        }

        XCTAssertEqual(store.acknowledged, [[firstRoute, latestRoute]])
        XCTAssertEqual(store.routes.map(\.0), [laterRoute])
    }

    func testInvalidLatestRouteIsRemovedBeforeOpeningOlderActiveNote() throws {
        let validRoute = UUID()
        let invalidRoute = UUID()
        let noteID = UUID()
        let store = RoutingStoreStub(routes: [
            (validRoute, noteID), (invalidRoute, nil)
        ])
        var opened: UUID?

        try PendingNoteRouter(repository: store).consumeLatest { opened = $0 }

        XCTAssertEqual(opened, noteID)
        XCTAssertEqual(store.acknowledged, [[invalidRoute], [validRoute]])
        XCTAssertTrue(store.routes.isEmpty)
    }

    func testSeveralInvalidLatestRoutesAreRemovedOneAtATime() throws {
        let validRoute = UUID()
        let missingRoute = UUID()
        let trashedRoute = UUID()
        let noteID = UUID()
        let store = RoutingStoreStub(routes: [
            (validRoute, noteID), (missingRoute, nil), (trashedRoute, nil)
        ])

        try PendingNoteRouter(repository: store).consumeLatest { XCTAssertEqual($0, noteID) }

        XCTAssertEqual(store.acknowledged, [[trashedRoute], [missingRoute], [validRoute]])
    }

    func testOpenFailureKeepsCapturedRoutes() {
        let routeID = UUID()
        let store = RoutingStoreStub(routes: [(routeID, UUID())])

        XCTAssertThrowsError(try PendingNoteRouter(repository: store).consumeLatest { _ in
            throw RouterTestFailure.failed
        })

        XCTAssertTrue(store.acknowledged.isEmpty)
        XCTAssertEqual(store.routes.map(\.0), [routeID])
    }
}

private enum RouterTestFailure: Error { case failed }

@MainActor
private final class RoutingStoreStub: PendingNoteRoutingStore {
    var routes: [(UUID, UUID?)]
    var acknowledged: [[UUID]] = []
    var events: [String] = []

    init(routes: [(UUID, UUID?)]) { self.routes = routes }

    func pendingRouteSnapshot() throws -> PendingRouteSnapshot {
        PendingRouteSnapshot(routeIDs: routes.map(\.0), noteID: routes.last?.1)
    }

    func acknowledge(routeIDs: [UUID]) throws {
        acknowledged.append(routeIDs)
        events.append("ack")
        routes.removeAll { routeIDs.contains($0.0) }
    }
}
