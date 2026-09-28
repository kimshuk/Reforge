import Foundation
import SwiftData

final class ContentNoteRepository: @unchecked Sendable {
    let container: ModelContainer
    let lock: SharedStoreLock

    init(container: ModelContainer, lock: SharedStoreLock) {
        self.container = container
        self.lock = lock
    }

    func find(sourceKey: String) throws -> StoredContentNote? {
        let context = ModelContext(container)
        return try findModel(sourceKey: sourceKey, in: context)?.stored
    }

    nonisolated func saveOrReuse(_ draft: ContentNoteDraft) throws -> SaveNoteOutcome {
        try lock.withLock {
            let context = ModelContext(container)
            if let existing = try findModel(sourceKey: draft.sourceKey, in: context) {
                try throwIfTaskCancelled()
                context.insert(PendingNoteRoute(noteId: existing.id))
                try context.save()
                return .alreadySaved(existing.stored)
            }

            try throwIfTaskCancelled()
            let note = ContentNote(draft: draft)
            context.insert(note)
            context.insert(PendingNoteRoute(noteId: note.id))
            try context.save()
            return .saved(note.stored)
        }
    }

    func enqueueRoute(noteID: UUID) throws {
        try lock.withLock {
            try throwIfTaskCancelled()
            let context = ModelContext(container)
            context.insert(PendingNoteRoute(noteId: noteID))
            try context.save()
        }
    }

    func pendingRouteSnapshot() throws -> PendingRouteSnapshot {
        let context = ModelContext(container)
        let descriptor = FetchDescriptor<PendingNoteRoute>(
            sortBy: [SortDescriptor(\PendingNoteRoute.createdAt)]
        )
        let routes = try context.fetch(descriptor)
        guard let latest = routes.last else {
            return PendingRouteSnapshot(routeIDs: [], note: nil)
        }
        let noteID = latest.noteId
        let noteDescriptor = FetchDescriptor<ContentNote>(
            predicate: #Predicate { $0.id == noteID }
        )
        let note = try context.fetch(noteDescriptor).first?.stored
        return PendingRouteSnapshot(routeIDs: routes.map(\.id), note: note)
    }

    func acknowledge(routeIDs: [UUID]) throws {
        guard !routeIDs.isEmpty else { return }
        let idSet = Set(routeIDs)
        try lock.withLock {
            let context = ModelContext(container)
            let routes = try context.fetch(FetchDescriptor<PendingNoteRoute>())
            for route in routes where idSet.contains(route.id) {
                context.delete(route)
            }
            try context.save()
        }
    }

    nonisolated private func findModel(
        sourceKey: String,
        in context: ModelContext
    ) throws -> ContentNote? {
        let descriptor = FetchDescriptor<ContentNote>(
            predicate: #Predicate { $0.sourceKey == sourceKey }
        )
        return try context.fetch(descriptor).first
    }

    nonisolated private func throwIfTaskCancelled() throws {
        let isCancelled = withUnsafeCurrentTask { task in
            task?.isCancelled ?? false
        }
        if isCancelled {
            throw CancellationError()
        }
    }
}
