import Foundation

protocol PendingNoteRoutingStore {
    func pendingRouteSnapshot() throws -> PendingRouteSnapshot
    func acknowledge(routeIDs: [UUID]) throws
}

extension ContentNoteRepository: PendingNoteRoutingStore {}

struct PendingNoteRouter {
    private let repository: any PendingNoteRoutingStore

    init(repository: any PendingNoteRoutingStore) {
        self.repository = repository
    }

    func consumeLatest(open: (UUID) throws -> Void) throws {
        while true {
            let snapshot = try repository.pendingRouteSnapshot()
            guard let latestRouteID = snapshot.routeIDs.last else { return }
            guard let noteID = snapshot.noteID else {
                try repository.acknowledge(routeIDs: [latestRouteID])
                continue
            }
            try open(noteID)
            try repository.acknowledge(routeIDs: snapshot.routeIDs)
            return
        }
    }
}
