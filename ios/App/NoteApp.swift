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
    private let analyzeService: AnalyzeService
    private let youtubeTitleService: YouTubeTitleService
    private let pendingNoteRouter: PendingNoteRouter

    init() {
        do {
            self.analyzeService = try URLSessionAnalyzeService(config: .default)
            self.youtubeTitleService = YouTubeOEmbedService()
            let container = try SharedModelContainer.makeAppGroupContainer()
            let repository = ContentNoteRepository(
                container: container,
                lock: try SharedModelContainer.appGroupLock()
            )
            self.pendingNoteRouter = PendingNoteRouter(repository: repository)
        } catch {
            fatalError("Failed to initialize AnalyzeService: \(error.localizedDescription)")
        }
    }

    var body: some Scene {
        WindowGroup {
            RootView(
                analyzeService: analyzeService,
                youtubeTitleService: youtubeTitleService,
                router: pendingNoteRouter
            )
        }
    }
}
