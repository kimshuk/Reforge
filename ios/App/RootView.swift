//
//  RootView.swift
//  NoteApp
//
//  Created by 김지수 on 3/7/26.
//

import SwiftUI

struct RootView: View {
    let analyzeService: AnalyzeService
    let youtubeTitleService: YouTubeTitleService

    var body: some View {
        NavigationStack {
            HomeView(
                viewModel: HomeViewModel(
                    analyzeService: analyzeService,
                    youtubeTitleService: youtubeTitleService
                )
            )
        }
    }
}
