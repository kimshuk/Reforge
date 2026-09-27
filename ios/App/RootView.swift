//
//  RootView.swift
//  NoteApp
//
//  Created by 김지수 on 3/7/26.
//

import SwiftUI

struct RootView: View {
    @Environment(\.scenePhase) private var scenePhase
    @StateObject private var viewModel: HomeViewModel
    private let router: PendingNoteRouter

    init(
        analyzeService: AnalyzeService,
        youtubeTitleService: YouTubeTitleService,
        router: PendingNoteRouter
    ) {
        _viewModel = StateObject(
            wrappedValue: HomeViewModel(
                analyzeService: analyzeService,
                youtubeTitleService: youtubeTitleService
            )
        )
        self.router = router
    }

    var body: some View {
        NavigationStack {
            HomeView(viewModel: viewModel)
        }
        .onChange(of: scenePhase) {
            guard scenePhase == .active else { return }
            try? router.consumeLatest { note in
                viewModel.applySharedNote(note)
            }
        }
    }
}
