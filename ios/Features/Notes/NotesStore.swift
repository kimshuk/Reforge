import Foundation

protocol NotesStore {
    func note(id: UUID) throws -> StoredContentNote?
    func activeNotes() throws -> [StoredContentNote]
    func trashedNotes() throws -> [StoredContentNote]
    func moveToTrash(noteID: UUID, at: Date) throws
    func restore(noteID: UUID) throws
    func deletePermanently(noteID: UUID) throws
    @discardableResult func purgeExpiredTrash(cutoff: Date) throws -> Int
}

extension ContentNoteRepository: NotesStore {}
