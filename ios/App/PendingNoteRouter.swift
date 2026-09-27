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

    func consumeLatest(apply: (StoredContentNote) throws -> Void) throws {
        let snapshot = try repository.pendingRouteSnapshot()
        guard !snapshot.routeIDs.isEmpty else { return }
        if let note = snapshot.note {
            try apply(note)
        }
        try repository.acknowledge(routeIDs: snapshot.routeIDs)
    }
}
