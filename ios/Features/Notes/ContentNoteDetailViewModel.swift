import Combine
import Foundation

@MainActor
final class ContentNoteDetailViewModel: ObservableObject {
    @Published private(set) var note: StoredContentNote?
    @Published private(set) var errorMessage = ""

    private let repository: NotesStore
    private let noteID: UUID

    init(repository: NotesStore, noteID: UUID) {
        self.repository = repository
        self.noteID = noteID
    }

    var thumbnailURL: URL? {
        guard let videoID = note?.videoId, !videoID.isEmpty else { return nil }
        return URL(string: "https://img.youtube.com/vi/\(videoID)/hqdefault.jpg")
    }

    func load() {
        do {
            let fetched = try repository.note(id: noteID)
            note = fetched?.trashedAt == nil ? fetched : nil
            errorMessage = ""
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func moveToTrash(at date: Date) -> Bool {
        guard note != nil else { return false }
        do {
            try repository.moveToTrash(noteID: noteID, at: date)
            note = nil
            errorMessage = ""
            return true
        } catch {
            errorMessage = error.localizedDescription
            return false
        }
    }
}
