import Foundation
import SwiftData

enum ContentNoteRepositoryError: Error, Equatable {
    case noteNotFound
}

final class ContentNoteRepository: @unchecked Sendable {
    let container: ModelContainer
    let lock: SharedStoreLock

    init(container: ModelContainer, lock: SharedStoreLock) {
        self.container = container
        self.lock = lock
    }

    nonisolated func prepareForShare(sourceKey: String) throws -> ShareNotePreparation {
        try lock.withLock {
            let context = ModelContext(container)
            guard let note = try findModel(sourceKey: sourceKey, in: context) else {
                return .absent
            }
            guard note.trashedAt == nil else {
                return .trashed(note.stored)
            }
            try throwIfTaskCancelled()
            context.insert(PendingNoteRoute(noteId: note.id))
            try context.save()
            return .activeRouted(note.stored)
        }
    }

    func note(id: UUID) throws -> StoredContentNote? {
        let context = ModelContext(container)
        return try findModel(id: id, in: context)?.stored
    }

    func activeNotes() throws -> [StoredContentNote] {
        let context = ModelContext(container)
        return try context.fetch(FetchDescriptor<ContentNote>())
            .filter { $0.trashedAt == nil }
            .sorted { $0.createdAt > $1.createdAt }
            .map(\.stored)
    }

    func trashedNotes() throws -> [StoredContentNote] {
        let context = ModelContext(container)
        return try context.fetch(FetchDescriptor<ContentNote>())
            .filter { $0.trashedAt != nil }
            .sorted { ($0.trashedAt ?? .distantPast) > ($1.trashedAt ?? .distantPast) }
            .map(\.stored)
    }

    nonisolated func saveOrReuse(_ draft: ContentNoteDraft) throws -> SaveNoteOutcome {
        try lock.withLock {
            let context = ModelContext(container)
            if let existing = try findModel(sourceKey: draft.sourceKey, in: context) {
                guard existing.trashedAt == nil else {
                    return .restoreRequired(existing.stored)
                }
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

    nonisolated func moveToTrash(noteID: UUID, at date: Date) throws {
        try lock.withLock {
            let context = ModelContext(container)
            guard let note = try findModel(id: noteID, in: context) else { return }
            try throwIfTaskCancelled()
            note.trashedAt = date
            try deleteRoutes(noteID: noteID, in: context)
            try context.save()
        }
    }

    func restore(noteID: UUID) throws {
        try lock.withLock {
            let context = ModelContext(container)
            guard let note = try findModel(id: noteID, in: context) else { return }
            try throwIfTaskCancelled()
            note.trashedAt = nil
            try context.save()
        }
    }

    func restoreAndEnqueueRoute(noteID: UUID) throws -> StoredContentNote {
        try lock.withLock {
            let context = ModelContext(container)
            guard let note = try findModel(id: noteID, in: context) else {
                throw ContentNoteRepositoryError.noteNotFound
            }
            try throwIfTaskCancelled()
            note.trashedAt = nil
            context.insert(PendingNoteRoute(noteId: noteID))
            try context.save()
            return note.stored
        }
    }

    func deletePermanently(noteID: UUID) throws {
        try lock.withLock {
            let context = ModelContext(container)
            guard let note = try findModel(id: noteID, in: context) else { return }
            try throwIfTaskCancelled()
            try deleteRoutes(noteID: noteID, in: context)
            context.delete(note)
            try context.save()
        }
    }

    @discardableResult
    func purgeExpiredTrash(cutoff: Date) throws -> Int {
        try lock.withLock {
            let context = ModelContext(container)
            let notes = try context.fetch(FetchDescriptor<ContentNote>())
            let expired = notes.filter { $0.trashedAt.map { $0 <= cutoff } ?? false }
            guard !expired.isEmpty else { return 0 }
            try throwIfTaskCancelled()
            let expiredIDs = Set(expired.map(\.id))
            let routes = try context.fetch(FetchDescriptor<PendingNoteRoute>())
            for route in routes where expiredIDs.contains(route.noteId) {
                context.delete(route)
            }
            for note in expired { context.delete(note) }
            try context.save()
            return expired.count
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

    nonisolated private func findModel(id: UUID, in context: ModelContext) throws -> ContentNote? {
        let descriptor = FetchDescriptor<ContentNote>(predicate: #Predicate { $0.id == id })
        return try context.fetch(descriptor).first
    }

    nonisolated private func deleteRoutes(noteID: UUID, in context: ModelContext) throws {
        let routes = try context.fetch(FetchDescriptor<PendingNoteRoute>())
        for route in routes where route.noteId == noteID {
            context.delete(route)
        }
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
