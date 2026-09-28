//
//  NoteApp.swift
//  NoteApp
//
//  Created by 김지수 on 3/7/26.
//

import SwiftUI
import SwiftData

@main
struct NoteApp: App {
    private let repository: ContentNoteRepository
    private let coordinator: AppCoordinator

    init() {
        do {
            let analyzeService = try URLSessionAnalyzeService(config: .default)
            let youtubeTitleService = YouTubeOEmbedService()
            let container = try SharedModelContainer.makeAppGroupContainer()
            let repository = ContentNoteRepository(
                container: container,
                lock: try SharedModelContainer.appGroupLock()
            )
            self.repository = repository
            self.coordinator = AppCoordinator(
                homeViewModel: HomeViewModel(
                    analyzeService: analyzeService,
                    youtubeTitleService: youtubeTitleService
                ),
                router: PendingNoteRouter(repository: repository),
                purgeExpiredTrash: { cutoff in
                    _ = try repository.purgeExpiredTrash(cutoff: cutoff)
                }
            )
        } catch {
            fatalError("Failed to initialize AnalyzeService: \(error.localizedDescription)")
        }
    }

    var body: some Scene {
        WindowGroup {
            RootView(coordinator: coordinator, repository: repository)
        }
    }
}
