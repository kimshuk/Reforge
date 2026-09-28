import SwiftUI

struct TrashView: View {
    @Environment(\.scenePhase) private var scenePhase
    @StateObject private var viewModel: TrashViewModel
    @State private var noteToDelete: StoredContentNote?

    private let now: Date

    init(repository: NotesStore, now: Date) {
        _viewModel = StateObject(wrappedValue: TrashViewModel(repository: repository))
        self.now = now
    }

    var body: some View {
        List {
            if !viewModel.errorMessage.isEmpty {
                Text(viewModel.errorMessage)
                    .foregroundStyle(.red)
            }

            if viewModel.notes.isEmpty {
                Text("Trash is empty.")
                    .foregroundStyle(.secondary)
            } else {
                ForEach(viewModel.notes, id: \.id) { note in
                    HStack {
                        Text(note.title)
                        Spacer()
                        Button("Restore") {
                            viewModel.restore(noteID: note.id)
                        }
                        .buttonStyle(.borderless)
                    }
                    .swipeActions {
                        Button("Delete", role: .destructive) {
                            noteToDelete = note
                        }
                    }
                }
            }
        }
        .navigationTitle("Trash")
        .alert(
            "Delete this note permanently? This can’t be undone.",
            isPresented: Binding(
                get: { noteToDelete != nil },
                set: { if !$0 { noteToDelete = nil } }
            )
        ) {
            Button("Cancel", role: .cancel) { noteToDelete = nil }
            Button("Delete", role: .destructive) {
                guard let note = noteToDelete else { return }
                viewModel.deletePermanently(noteID: note.id)
                noteToDelete = nil
            }
        }
        .onAppear { viewModel.load(now: now) }
        .onChange(of: scenePhase) {
            if scenePhase == .active { viewModel.load(now: Date()) }
        }
    }
}
