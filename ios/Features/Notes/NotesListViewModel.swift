import Combine
import Foundation

@MainActor
final class NotesListViewModel: ObservableObject {
    @Published private(set) var notes: [StoredContentNote] = []
    @Published private(set) var errorMessage = ""

    private let repository: NotesStore

    init(repository: NotesStore) {
        self.repository = repository
    }

    func load() {
        do {
            notes = try repository.activeNotes()
            errorMessage = ""
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func moveToTrash(noteID: UUID, at date: Date) {
        do {
            try repository.moveToTrash(noteID: noteID, at: date)
            load()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
