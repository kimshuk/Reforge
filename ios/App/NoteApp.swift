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

    init() {
        do {
            self.analyzeService = try URLSessionAnalyzeService(config: .default)
            self.youtubeTitleService = YouTubeOEmbedService()
        } catch {
            fatalError("Failed to initialize AnalyzeService: \(error.localizedDescription)")
        }
    }

    var body: some Scene {
        WindowGroup {
            RootView(analyzeService: analyzeService, youtubeTitleService: youtubeTitleService)
        }
    }
}
