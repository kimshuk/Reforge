//
//  RootView.swift
//  NoteApp
//
//  Created by 김지수 on 3/7/26.
//

import SwiftUI

struct RootView: View {
    @Environment(\.scenePhase) private var scenePhase
    @StateObject private var coordinator: AppCoordinator
    private let repository: ContentNoteRepository

    init(coordinator: AppCoordinator, repository: ContentNoteRepository) {
        _coordinator = StateObject(wrappedValue: coordinator)
        self.repository = repository
    }

    var body: some View {
        TabView(selection: $coordinator.selectedTab) {
            NavigationStack {
                HomeView(viewModel: coordinator.homeViewModel)
            }
            .tabItem { Label("Home", systemImage: "house") }
            .tag(AppTab.home)

            NavigationStack(path: $coordinator.notesPath) {
                NotesListView(
                    repository: repository,
                    onOpenNote: { coordinator.openNote($0) },
                    onOpenTrash: { coordinator.notesPath.append(.trash) }
                )
                .navigationDestination(for: NotesRoute.self) { route in
                    switch route {
                    case .detail(let noteID):
                        ContentNoteDetailView(
                            repository: repository,
                            noteID: noteID,
                            onAnalyze: { note in
                                Task { await coordinator.analyze(note) }
                            },
                            onDeleted: {
                                if coordinator.notesPath.last == .detail(noteID) {
                                    coordinator.notesPath.removeLast()
                                }
                            }
                        )
                    case .trash:
                        TrashView(repository: repository, now: Date())
                    }
                }
            }
            .tabItem { Label("My Notes", systemImage: "note.text") }
            .tag(AppTab.myNotes)
        }
        .task { coordinator.activate() }
        .onChange(of: scenePhase) {
            if scenePhase == .active { coordinator.activate() }
        }
    }
}
