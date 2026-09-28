import SwiftUI

struct ContentNoteDetailView: View {
    @Environment(\.scenePhase) private var scenePhase
    @StateObject private var viewModel: ContentNoteDetailViewModel
    @State private var showsTrashConfirmation = false

    private let onAnalyze: (StoredContentNote) -> Void
    private let onDeleted: () -> Void

    init(
        repository: NotesStore,
        noteID: UUID,
        onAnalyze: @escaping (StoredContentNote) -> Void,
        onDeleted: @escaping () -> Void
    ) {
        _viewModel = StateObject(
            wrappedValue: ContentNoteDetailViewModel(repository: repository, noteID: noteID)
        )
        self.onAnalyze = onAnalyze
        self.onDeleted = onDeleted
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                if !viewModel.errorMessage.isEmpty {
                    Text(viewModel.errorMessage)
                        .foregroundStyle(.red)
                }

                if let note = viewModel.note {
                    Text(note.title)
                        .font(.title2.bold())

                    if let thumbnailURL = viewModel.thumbnailURL {
                        AsyncImage(url: thumbnailURL) { image in
                            image.resizable().scaledToFill()
                        } placeholder: {
                            Color(.systemGray5)
                        }
                        .frame(maxWidth: .infinity)
                        .aspectRatio(16 / 9, contentMode: .fit)
                        .clipped()
                    }

                    Link("Open in YouTube", destination: note.canonicalURL)

                    if let languageCode = note.transcriptLanguageCode {
                        Text("Language: \(languageCode)")
                            .foregroundStyle(.secondary)
                    }
                    if let isGenerated = note.transcriptIsGenerated {
                        Text(isGenerated ? "Generated" : "Not generated")
                            .foregroundStyle(.secondary)
                    }

                    Text(note.transcriptText)
                        .frame(maxWidth: .infinity, alignment: .leading)

                    Button("Analyze") {
                        onAnalyze(note)
                    }
                    .buttonStyle(.borderedProminent)

                    Button("Move to Trash", role: .destructive) {
                        showsTrashConfirmation = true
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding()
        }
        .navigationTitle("Note")
        .alert(
            "Move this note to Trash? You can restore it for 30 days.",
            isPresented: $showsTrashConfirmation
        ) {
            Button("Cancel", role: .cancel) {}
            Button("Move to Trash", role: .destructive) {
                if viewModel.moveToTrash(at: Date()) { onDeleted() }
            }
        }
        .onAppear { reload() }
        .onChange(of: scenePhase) {
            if scenePhase == .active { reload() }
        }
    }

    private func reload() {
        viewModel.load()
        if viewModel.note == nil && viewModel.errorMessage.isEmpty {
            onDeleted()
        }
    }
}
