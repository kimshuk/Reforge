import Foundation
import SwiftData

@Model
final class PendingNoteRoute {
    var id: UUID
    var noteId: UUID
    var createdAt: Date

    init(id: UUID = UUID(), noteId: UUID, createdAt: Date = Date()) {
        self.id = id
        self.noteId = noteId
        self.createdAt = createdAt
    }
}

struct PendingRouteSnapshot: Equatable, Sendable {
    let routeIDs: [UUID]
    let noteID: UUID?
}
