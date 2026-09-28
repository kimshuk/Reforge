import SwiftUI

struct NotesListView: View {
    @Environment(\.scenePhase) private var scenePhase
    @StateObject private var viewModel: NotesListViewModel
    @State private var noteToTrash: StoredContentNote?

    private let onOpenNote: (UUID) -> Void
    private let onOpenTrash: () -> Void

    init(
        repository: NotesStore,
        onOpenNote: @escaping (UUID) -> Void,
        onOpenTrash: @escaping () -> Void
    ) {
        _viewModel = StateObject(wrappedValue: NotesListViewModel(repository: repository))
        self.onOpenNote = onOpenNote
        self.onOpenTrash = onOpenTrash
    }

    var body: some View {
        List {
            if !viewModel.errorMessage.isEmpty {
                Text(viewModel.errorMessage)
                    .foregroundStyle(.red)
            }

            if viewModel.notes.isEmpty {
                Text("No saved notes yet.")
                    .foregroundStyle(.secondary)
            } else {
                ForEach(viewModel.notes, id: \.id) { note in
                    Button {
                        onOpenNote(note.id)
                    } label: {
                        Text(note.title)
                            .foregroundStyle(.primary)
                    }
                    .swipeActions {
                        Button("Move to Trash", role: .destructive) {
                            noteToTrash = note
                        }
                    }
                }
            }
        }
        .navigationTitle("My Notes")
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button("Trash", systemImage: "trash") {
                    onOpenTrash()
                }
            }
        }
        .alert(
            "Move this note to Trash? You can restore it for 30 days.",
            isPresented: Binding(
                get: { noteToTrash != nil },
                set: { if !$0 { noteToTrash = nil } }
            )
        ) {
            Button("Cancel", role: .cancel) { noteToTrash = nil }
            Button("Move to Trash", role: .destructive) {
                guard let note = noteToTrash else { return }
                viewModel.moveToTrash(noteID: note.id, at: Date())
                noteToTrash = nil
            }
        }
        .onAppear { viewModel.load() }
        .onChange(of: scenePhase) {
            if scenePhase == .active { viewModel.load() }
        }
    }
}
