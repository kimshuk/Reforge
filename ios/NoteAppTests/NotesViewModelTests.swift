import XCTest
import SwiftUI
import UIKit
@testable import NoteApp

@MainActor
final class NotesViewModelTests: XCTestCase {
    func testListLoadsActiveNotesAndRefreshesAfterMoveToTrash() {
        let older = makeNote(title: "Older", createdAt: Date(timeIntervalSince1970: 100))
        let newer = makeNote(title: "Newer", createdAt: Date(timeIntervalSince1970: 200))
        let store = MemoryNotesStore(active: [newer, older])
        let viewModel = NotesListViewModel(repository: store)

        viewModel.load()
        XCTAssertEqual(viewModel.notes.map(\.id), [newer.id, older.id])

        viewModel.moveToTrash(noteID: newer.id, at: Date(timeIntervalSince1970: 300))
        XCTAssertEqual(viewModel.notes.map(\.id), [older.id])
    }

    func testDetailDerivesThumbnailAndPreservesSnapshotForAnalyze() {
        let note = makeNote(title: "Saved video")
        let store = MemoryNotesStore(active: [note])
        let viewModel = ContentNoteDetailViewModel(repository: store, noteID: note.id)

        viewModel.load()
        XCTAssertEqual(viewModel.note, note)
        XCTAssertEqual(viewModel.thumbnailURL?.absoluteString, "https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg")

        let analyzeSnapshot = viewModel.note
        store.active.removeAll()
        XCTAssertEqual(analyzeSnapshot?.title, "Saved video")
        XCTAssertEqual(analyzeSnapshot?.canonicalURL, note.canonicalURL)
    }

    func testDetailClosesWhenNoteIsMissingOrTrashed() {
        let note = makeNote()
        let store = MemoryNotesStore(active: [note])
        let viewModel = ContentNoteDetailViewModel(repository: store, noteID: note.id)

        viewModel.load()
        XCTAssertNotNil(viewModel.note)
        store.active.removeAll()
        viewModel.load()
        XCTAssertNil(viewModel.note)

        store.trash = [makeNote(id: note.id, trashedAt: Date(timeIntervalSince1970: 200))]
        viewModel.load()
        XCTAssertNil(viewModel.note)
    }

    func testTrashLoadPurgesAtThirtyDayCutoffBeforeListing() {
        let now = Date(timeIntervalSince1970: 100 * 86_400)
        let cutoff = now.addingTimeInterval(-30 * 86_400)
        let expired = makeNote(title: "Expired", trashedAt: cutoff)
        let older = makeNote(title: "Older", trashedAt: cutoff.addingTimeInterval(1))
        let newer = makeNote(title: "Newer", trashedAt: now)
        let store = MemoryNotesStore(trash: [older, expired, newer])
        let viewModel = TrashViewModel(repository: store)

        viewModel.load(now: now)

        XCTAssertEqual(viewModel.notes.map(\.id), [newer.id, older.id])
        XCTAssertFalse(store.trash.contains { $0.id == expired.id })
    }

    func testRestoreAndPermanentDeleteRefreshTrashRows() {
        let now = Date(timeIntervalSince1970: 100 * 86_400)
        let first = makeNote(title: "Restore", trashedAt: now.addingTimeInterval(-86_400))
        let second = makeNote(title: "Delete", trashedAt: now)
        let store = MemoryNotesStore(trash: [first, second])
        let viewModel = TrashViewModel(repository: store)
        viewModel.load(now: now)

        viewModel.restore(noteID: first.id)
        XCTAssertEqual(viewModel.notes.map(\.id), [second.id])
        XCTAssertTrue(store.active.contains { $0.id == first.id })

        viewModel.deletePermanently(noteID: second.id)
        XCTAssertTrue(viewModel.notes.isEmpty)
        XCTAssertTrue(store.trash.isEmpty)
    }

    func testStoreFailureKeepsPreviousVisibleState() {
        let now = Date(timeIntervalSince1970: 100 * 86_400)
        let active = makeNote(title: "Active")
        let trashed = makeNote(title: "Trashed", trashedAt: now)
        let store = MemoryNotesStore(active: [active], trash: [trashed])
        let list = NotesListViewModel(repository: store)
        let detail = ContentNoteDetailViewModel(repository: store, noteID: active.id)
        let trash = TrashViewModel(repository: store)
        list.load()
        detail.load()
        trash.load(now: now)

        store.error = StoreFailure.unavailable
        list.load()
        detail.load()
        trash.load(now: now)
        list.moveToTrash(noteID: active.id, at: now)
        XCTAssertFalse(detail.moveToTrash(at: now))
        trash.restore(noteID: trashed.id)
        trash.deletePermanently(noteID: trashed.id)

        XCTAssertEqual(list.notes, [active])
        XCTAssertEqual(detail.note, active)
        XCTAssertEqual(trash.notes, [trashed])
        XCTAssertEqual(list.errorMessage, "Store unavailable")
        XCTAssertEqual(detail.errorMessage, "Store unavailable")
        XCTAssertEqual(trash.errorMessage, "Store unavailable")
    }

    func testTrashForegroundRefreshUsesCurrentCutoff() {
        let activationTime = Date()
        let expired = makeNote(
            title: "Expired while backgrounded",
            trashedAt: activationTime.addingTimeInterval(-31 * 86_400)
        )
        let store = MemoryNotesStore(trash: [expired])
        let phase = TrashScenePhase()
        let host = UIHostingController(rootView: TrashSceneHarness(
            store: store,
            initialNow: Date(timeIntervalSince1970: 100),
            phase: phase
        ))
        let window = UIWindow(frame: UIScreen.main.bounds)
        window.rootViewController = host
        window.makeKeyAndVisible()
        RunLoop.main.run(until: Date().addingTimeInterval(0.05))
        XCTAssertEqual(store.trash.map(\.id), [expired.id])

        phase.value = .background
        RunLoop.main.run(until: Date().addingTimeInterval(0.05))
        phase.value = .active
        RunLoop.main.run(until: Date().addingTimeInterval(0.05))

        XCTAssertTrue(store.trash.isEmpty)
        window.isHidden = true
    }
}

@MainActor
private final class TrashScenePhase: ObservableObject {
    @Published var value: ScenePhase = .active
}

private struct TrashSceneHarness: View {
    let store: MemoryNotesStore
    let initialNow: Date
    @ObservedObject var phase: TrashScenePhase

    var body: some View {
        TrashView(repository: store, now: initialNow)
            .environment(\.scenePhase, phase.value)
    }
}

private enum StoreFailure: LocalizedError {
    case unavailable

    var errorDescription: String? { "Store unavailable" }
}

private func makeNote(
    id: UUID = UUID(),
    title: String = "Note",
    createdAt: Date = Date(timeIntervalSince1970: 100),
    trashedAt: Date? = nil
) -> StoredContentNote {
    let videoID = "dQw4w9WgXcQ"
    return StoredContentNote(
        id: id, sourceKey: "youtube:\(videoID)", sourceType: "youtube",
        videoId: videoID,
        sourceURL: URL(string: "https://youtu.be/\(videoID)")!,
        canonicalURL: URL(string: "https://www.youtube.com/watch?v=\(videoID)")!,
        title: title, transcriptId: "transcript-1", transcriptText: "Full transcript",
        transcriptLanguageCode: "en", transcriptIsGenerated: true,
        createdAt: createdAt, trashedAt: trashedAt
    )
}

private final class MemoryNotesStore: NotesStore {
    var active: [StoredContentNote]
    var trash: [StoredContentNote]
    var error: Error?

    init(active: [StoredContentNote] = [], trash: [StoredContentNote] = []) {
        self.active = active
        self.trash = trash
    }

    func note(id: UUID) throws -> StoredContentNote? {
        try failIfNeeded()
        return (active + trash).first { $0.id == id }
    }

    func activeNotes() throws -> [StoredContentNote] {
        try failIfNeeded()
        return active
    }

    func trashedNotes() throws -> [StoredContentNote] {
        try failIfNeeded()
        return trash
    }

    func moveToTrash(noteID: UUID, at date: Date) throws {
        try failIfNeeded()
        guard let index = active.firstIndex(where: { $0.id == noteID }) else { return }
        let note = active.remove(at: index)
        trash.append(copy(note, trashedAt: date))
    }

    func restore(noteID: UUID) throws {
        try failIfNeeded()
        guard let index = trash.firstIndex(where: { $0.id == noteID }) else { return }
        let note = trash.remove(at: index)
        active.append(copy(note, trashedAt: nil))
    }

    func deletePermanently(noteID: UUID) throws {
        try failIfNeeded()
        trash.removeAll { $0.id == noteID }
    }

    func purgeExpiredTrash(cutoff: Date) throws -> Int {
        try failIfNeeded()
        let oldCount = trash.count
        trash.removeAll { ($0.trashedAt ?? .distantFuture) <= cutoff }
        return oldCount - trash.count
    }

    private func failIfNeeded() throws {
        if let error { throw error }
    }

    private func copy(_ note: StoredContentNote, trashedAt: Date?) -> StoredContentNote {
        StoredContentNote(
            id: note.id, sourceKey: note.sourceKey, sourceType: note.sourceType,
            videoId: note.videoId, sourceURL: note.sourceURL,
            canonicalURL: note.canonicalURL, title: note.title,
            transcriptId: note.transcriptId, transcriptText: note.transcriptText,
            transcriptLanguageCode: note.transcriptLanguageCode,
            transcriptIsGenerated: note.transcriptIsGenerated,
            createdAt: note.createdAt, trashedAt: trashedAt
        )
    }
}
