//
//  HomeViewModel.swift
//  NoteApp
//
//  Created by 김지수 on 3/7/26.
//

import Foundation
import Combine

@MainActor
final class HomeViewModel: ObservableObject {
    @Published var titleInput: String = ""
    @Published var youtubeLink: String = ""
    @Published var isLoading: Bool = false
    @Published var errorMessage: String = ""
    @Published var analysisResult: AnalyzeResponse?
    @Published var videoUnavailableReason: VideoUnavailableReason?

    private let analyzeService: AnalyzeService
    private let youtubeTitleService: YouTubeTitleService
    private var autoFillTask: Task<Void, Never>?
    private var lastAutoFilledURL: String = ""

    var shouldShowTitleArea: Bool {
        let trimmed = youtubeLink.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return false }
        guard isYouTubeLink(trimmed) else { return false }
        return videoUnavailableReason == nil
    }

    var titleDisplayText: String {
        let trimmed = titleInput.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? "Loading title..." : trimmed
    }

    init(analyzeService: AnalyzeService, youtubeTitleService: YouTubeTitleService) {
        self.analyzeService = analyzeService
        self.youtubeTitleService = youtubeTitleService
    }

    func validateYoutubeLink() {
        let trimmed = youtubeLink.trimmingCharacters(in: .whitespacesAndNewlines)

        guard let url = URL(string: trimmed), let host = url.host else {
            errorMessage = "Please enter a valid URL."
            return
        }

        let isYoutubeHost = host.contains("youtube.com") || host.contains("youtu.be")
        errorMessage = isYoutubeHost ? "" : "URL is not a YouTube link."
    }

    func handleYouTubeLinkChange() {
        autoFillTask?.cancel()
        videoUnavailableReason = nil

        let trimmedURL = youtubeLink.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmedURL.isEmpty {
            titleInput = ""
            lastAutoFilledURL = ""
            errorMessage = ""
            return
        }

        guard isYouTubeLink(trimmedURL) else {
            lastAutoFilledURL = ""
            return
        }

        if lastAutoFilledURL != trimmedURL {
            titleInput = ""
        }

        autoFillTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 500_000_000)
            guard !Task.isCancelled else { return }
            await self?.autoFillTitleIfPossible(for: trimmedURL)
        }
    }

    func analyze() async {
        let trimmedTitle = titleInput.trimmingCharacters(in: .whitespacesAndNewlines)
        let trimmedURL = youtubeLink.trimmingCharacters(in: .whitespacesAndNewlines)

        guard !trimmedTitle.isEmpty else {
            errorMessage = "Please enter a title."
            return
        }

        guard let url = URL(string: trimmedURL), let host = url.host else {
            errorMessage = "Please enter a valid YouTube URL."
            return
        }

        guard host.contains("youtube.com") || host.contains("youtu.be") else {
            errorMessage = "URL is not a YouTube link."
            return
        }

        if let reason = videoUnavailableReason {
            errorMessage = reason.userMessage
            return
        }

        isLoading = true
        errorMessage = ""

        do {
            let result = try await analyzeService.analyzeYouTube(title: trimmedTitle, youtubeUrl: trimmedURL)
            analysisResult = result
        } catch {
            errorMessage = error.localizedDescription
        }

        isLoading = false
    }

    private func autoFillTitleIfPossible(for youtubeURL: String) async {
        do {
            let availability = try await youtubeTitleService.checkAvailability(for: youtubeURL)
            guard !Task.isCancelled else { return }

            let currentURL = youtubeLink.trimmingCharacters(in: .whitespacesAndNewlines)
            guard currentURL == youtubeURL else { return }

            switch availability {
            case .available(let title):
                videoUnavailableReason = nil
                titleInput = title
                lastAutoFilledURL = youtubeURL
                errorMessage = ""
            case .unavailable(let reason):
                videoUnavailableReason = reason
                titleInput = ""
                lastAutoFilledURL = ""
                errorMessage = reason.userMessage
            }
        } catch {
            // Keep this non-blocking; backend remains source of truth.
        }
    }

    private func isYouTubeLink(_ value: String) -> Bool {
        guard let url = URL(string: value), let host = url.host else {
            return false
        }
        return host.contains("youtube.com") || host.contains("youtu.be")
    }
}
