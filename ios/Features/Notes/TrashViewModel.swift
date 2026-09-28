import Combine
import Foundation

@MainActor
final class TrashViewModel: ObservableObject {
    @Published private(set) var notes: [StoredContentNote] = []
    @Published private(set) var errorMessage = ""

    private let repository: NotesStore

    init(repository: NotesStore) {
        self.repository = repository
    }

    func load(now: Date) {
        do {
            try repository.purgeExpiredTrash(cutoff: now.addingTimeInterval(-30 * 86_400))
            try refresh()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func restore(noteID: UUID) {
        do {
            try repository.restore(noteID: noteID)
            try refresh()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func deletePermanently(noteID: UUID) {
        do {
            try repository.deletePermanently(noteID: noteID)
            try refresh()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func refresh() throws {
        notes = try repository.trashedNotes().sorted {
            ($0.trashedAt ?? .distantPast) > ($1.trashedAt ?? .distantPast)
        }
        errorMessage = ""
    }
}
