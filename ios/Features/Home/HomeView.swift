//
//  HomeView.swift
//  NoteApp
//
//  Created by 김지수 on 3/7/26.
//

import SwiftUI
import Combine
import UIKit

struct HomeView: View {
    private enum Field: Hashable {
        case title
        case youtubeLink
    }

    @StateObject private var viewModel: HomeViewModel
    @StateObject private var keyboardObserver = KeyboardObserver()
    @State private var expandedCategoryTitle: String?
    @State private var selectedKeywordTermByCategory: [String: Set<String>] = [:]
    @State private var keywordDisplayLevelByCategory: [String: [String: Int]] = [:]
    @FocusState private var focusedField: Field?

    init(viewModel: HomeViewModel) {
        _viewModel = StateObject(wrappedValue: viewModel)
    }
    
    var body: some View {
        GeometryReader { geometry in
            ZStack {
                Color.clear
                    .contentShape(Rectangle())
                    .onTapGesture {
                        focusedField = nil
                    }

                ScrollView(showsIndicators: false) {
                    VStack(alignment: .leading, spacing: 16) {
                        if viewModel.shouldShowTitleArea {
                            VStack(alignment: .leading, spacing: 12) {
                                Text("Video title")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                TextField("Video title", text: $viewModel.titleInput)
                                    .textInputAutocapitalization(.sentences)
                                    .autocorrectionDisabled(false)
                                    .focused($focusedField, equals: .title)
                                    .disabled(viewModel.isLoading)
                                    .padding(12)
                                    .background(Color(.systemGray6))
                                    .clipShape(RoundedRectangle(cornerRadius: 10))

                                if let thumbnailURL = viewModel.youtubeThumbnailURL {
                                    let width = geometry.size.width * 0.7
                                    let height = width * 9 / 16
                                    
                                    AsyncImage(url: thumbnailURL) { phase in
                                        switch phase {
                                        case .empty:
                                            thumbnailPlaceholder
                                        case .success(let image):
                                            image
                                                .resizable()
                                                .scaledToFill()
                                        case .failure:
                                            thumbnailPlaceholder
                                        @unknown default:
                                            thumbnailPlaceholder
                                        }
                                    }
                                    .frame(width: width, height: height)
                                    .clipped()
                                    .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                                    .frame(maxWidth: .infinity)
                                }
                            }
                        }

                        if !viewModel.errorMessage.isEmpty {
                            Text(viewModel.errorMessage)
                                .font(.footnote)
                                .foregroundStyle(.red)
                        }

                        if let result = viewModel.analysisResult, !result.categories.isEmpty {
                            categorySection(for: result)
                        } else if viewModel.youtubeLink.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                            VStack(spacing: 8) {
                                Text("Add a YouTube link to get started")
                                    .font(.title3.weight(.semibold))
                                    .multilineTextAlignment(.center)

                                Text("Paste a video URL in the field below to analyze it.")
                                    .font(.body)
                                    .foregroundStyle(.secondary)
                                    .multilineTextAlignment(.center)
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.top, 120)
                        }
                    }
                }
                .padding()
                .frame(maxWidth: .infinity, alignment: .topLeading)
                .ignoresSafeArea(.keyboard)
            }
            .overlay(alignment: .bottom) {
                bottomFloatingBar
                    .padding(.horizontal, 16)
                    .padding(.bottom, bottomBarPadding(in: geometry))
                    .animation(.easeOut(duration: keyboardObserver.animationDuration), value: keyboardObserver.visibleHeight)
            }
            .overlay {
                if viewModel.isLoading {
                    loadingOverlay
                }
            }
        }
        .onChange(of: viewModel.analysisResult) {
            configureCategorySelection(for: viewModel.analysisResult)
        }
    }

    private func bottomBarPadding(in geometry: GeometryProxy) -> CGFloat {
        let bottomInset = geometry.safeAreaInsets.bottom
        let keyboardLift = max(0, keyboardObserver.visibleHeight - bottomInset)
        return 12 + keyboardLift
    }

    private var thumbnailPlaceholder: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .fill(Color(.systemGray6))

            Image(systemName: "photo")
                .font(.system(size: 28, weight: .medium))
                .foregroundStyle(.secondary)
        }
    }

    private var loadingOverlay: some View {
        ZStack {
            Rectangle()
                .fill(.ultraThinMaterial)
                .ignoresSafeArea()

            VStack(spacing: 22) {
                ZStack {
                    Circle()
                        .fill(
                            LinearGradient(
                                colors: [Color.blue.opacity(0.18), Color.cyan.opacity(0.08)],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                        .frame(width: 110, height: 110)

                    Image(systemName: "play.rectangle.on.rectangle")
                        .font(.system(size: 40, weight: .medium))
                        .foregroundStyle(.blue)
                }

                VStack(spacing: 8) {
                    Text("Analyzing Video")
                        .font(.system(size: 26, weight: .bold))

                    Text(viewModel.loadingStatusMessage.isEmpty ? "Preparing analysis." : viewModel.loadingStatusMessage)
                        .font(.system(size: 17, weight: .medium))
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                        .frame(maxWidth: 280)
                }

                HStack(spacing: 8) {
                    ForEach(Array(loadingStages.indices), id: \.self) { index in
                        Capsule()
                            .fill(index <= currentLoadingStageIndex ? Color.blue : Color(.systemGray4))
                            .frame(width: index == currentLoadingStageIndex ? 28 : 8, height: 8)
                            .animation(.easeInOut(duration: 0.2), value: currentLoadingStageIndex)
                    }
                }

                ProgressView()
                    .progressViewStyle(.circular)
                    .tint(.blue)
                    .scaleEffect(1.2)
            }
            .padding(.horizontal, 28)
            .padding(.vertical, 34)
            .frame(maxWidth: 340)
            .background(
                RoundedRectangle(cornerRadius: 32, style: .continuous)
                    .fill(Color(.systemBackground).opacity(0.96))
            )
            .overlay {
                RoundedRectangle(cornerRadius: 32, style: .continuous)
                    .strokeBorder(Color.white.opacity(0.55), lineWidth: 1)
            }
            .shadow(color: .black.opacity(0.08), radius: 24, y: 12)
        }
        .transition(.opacity)
    }

    private func categorySection(for result: AnalyzeResponse) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 16) {
                    ForEach(result.categories, id: \.title) { category in
                        Button {
                            toggleExpandedCategory(category)
                        } label: {
                            VStack(spacing: 6) {
                                Text(category.title)
                                    .font(.system(size: 16, weight: .semibold))
                                    .foregroundStyle(
                                        expandedCategoryTitle == category.title
                                        ? Color(.label)
                                        : Color(.secondaryLabel)
                                    )
                                    .lineLimit(1)

                                Capsule()
                                    .fill(
                                        expandedCategoryTitle == category.title
                                        ? Color.accentColor
                                        : Color.clear
                                    )
                                    .frame(height: 4)
                            }
                            .padding(.horizontal, 14)
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(.vertical, 2)
            }

            if let expanded = expandedCategory(in: result) {
                PillFlowLayout(itemSpacing: 10, rowSpacing: 10) {
                    ForEach(expanded.keywords, id: \.term) { keyword in
                        keywordPill(keyword, in: expanded.title)
                    }
                }
                .padding(.horizontal, 18)
                .padding(.vertical, 20)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(
                    RoundedRectangle(cornerRadius: 28, style: .continuous)
                        .fill(Color(.systemGray6))
                )
            }

            selectedKeywordsSection(for: result)
        }
        .padding(.top, 4)
    }

    @ViewBuilder
    private func selectedKeywordsSection(for result: AnalyzeResponse) -> some View {
        let categoriesWithSelections = result.categories.compactMap { category -> (AnalyzeCategory, [AnalyzeKeyword])? in
            let selected = category.keywords.filter {
                selectedKeywordTermByCategory[category.title]?.contains($0.term) ?? false
            }
            return selected.isEmpty ? nil : (category, selected)
        }
        if !categoriesWithSelections.isEmpty {
            VStack(alignment: .leading, spacing: 16) {
                ForEach(categoriesWithSelections, id: \.0.title) { category, keywords in
                    selectedCategoryGroup(category: category, keywords: keywords)
                }
                Spacer(minLength: 84)
            }
        }
    }

    private func selectedCategoryGroup(category: AnalyzeCategory, keywords: [AnalyzeKeyword]) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(category.title)
                .font(.system(size: 15, weight: .semibold))
            ForEach(keywords, id: \.term) { keyword in
                selectedKeywordRow(keyword: keyword, categoryTitle: category.title)
            }
        }
    }

    private func selectedKeywordRow(keyword: AnalyzeKeyword, categoryTitle: String) -> some View {
        let level = keywordDisplayLevelByCategory[categoryTitle]?[keyword.term] ?? 1
        let levelText = keywordLevelText(for: keyword, level: level)
        return HStack(alignment: .top, spacing: 8) {
            (Text("- ").foregroundStyle(.secondary) + Text(keyword.term).fontWeight(.semibold).foregroundStyle(.primary) + Text(": \(levelText)").foregroundStyle(.secondary))
                .font(.system(size: 14))
                .fixedSize(horizontal: false, vertical: true)
            Spacer()
            if level < 3 {
                Button {
                    keywordDisplayLevelByCategory[categoryTitle, default: [:]][keyword.term] = level + 1
                } label: {
                    Text("expand")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundStyle(Color.accentColor)
                }
                .buttonStyle(.plain)
            }
            Button {
                selectedKeywordTermByCategory[categoryTitle]?.remove(keyword.term)
                keywordDisplayLevelByCategory[categoryTitle]?.removeValue(forKey: keyword.term)
            } label: {
                Image(systemName: "xmark")
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundStyle(.secondary)
                    .padding(4)
            }
            .buttonStyle(.plain)
        }
    }

    private func keywordLevelText(for keyword: AnalyzeKeyword, level: Int) -> String {
        switch level {
        case 2: return keyword.level2
        case 3: return keyword.level3
        default: return keyword.level1
        }
    }

    private func keywordPill(_ keyword: AnalyzeKeyword, in categoryTitle: String) -> some View {
        let isSelected = selectedKeywordTermByCategory[categoryTitle]?.contains(keyword.term) ?? false

        return Button {
            if !isSelected {
                selectedKeywordTermByCategory[categoryTitle, default: []].insert(keyword.term)
                keywordDisplayLevelByCategory[categoryTitle, default: [:]][keyword.term] = 1
            }
        } label: {
            HStack(spacing: 6) {
                if isSelected {
                    Image(systemName: "checkmark")
                        .font(.system(size: 8, weight: .bold))
                }

                Text(keyword.term)
                    .font(.system(size: 10, weight: .medium))
                    .lineLimit(1)
                    .fixedSize(horizontal: true, vertical: false)
            }
            .foregroundStyle(isSelected ? Color.white : Color.accentColor)
            .padding(.leading, isSelected ? 12 : 14)
            .padding(.trailing, 14)
            .padding(.vertical, 8)
            .background(
                Capsule(style: .continuous)
                    .fill(isSelected ? Color.accentColor : Color(.systemBackground))
            )
            .overlay {
                Capsule(style: .continuous)
                    .stroke(Color.accentColor, lineWidth: 1)
            }
        }
        .buttonStyle(.plain)
    }

    private func expandedCategory(in result: AnalyzeResponse) -> AnalyzeCategory? {
        if let expandedCategoryTitle,
           let category = result.categories.first(where: { $0.title == expandedCategoryTitle }) {
            return category
        }

        return nil
    }

    private func toggleExpandedCategory(_ category: AnalyzeCategory) {
        if expandedCategoryTitle == category.title {
            expandedCategoryTitle = nil
            return
        }

        expandedCategoryTitle = category.title
    }

    private func configureCategorySelection(for result: AnalyzeResponse?) {
        expandedCategoryTitle = nil
        selectedKeywordTermByCategory.removeAll()
        keywordDisplayLevelByCategory.removeAll()
    }

    private var loadingStages: [String] {
        [
            "started",
            "fetching_transcript",
            "sanitizing_transcript",
            "transcript_ready",
            "storing_transcript",
            "analyzing_categories",
            "completed"
        ]
    }

    private var currentLoadingStageIndex: Int {
        guard let index = loadingStages.firstIndex(of: viewModel.loadingStage) else {
            return 0
        }
        return index
    }

    private var bottomFloatingBar: some View {
        HStack(spacing: 14) {
            HStack(spacing: 12) {
                TextField("Paste YouTube URL", text: $viewModel.youtubeLink)
                    .padding(.leading, 12)
                    .textInputAutocapitalization(.never)
                    .keyboardType(.URL)
                    .autocorrectionDisabled()
                    .font(.system(size: 18, weight: .medium))
                    .focused($focusedField, equals: .youtubeLink)
                    .disabled(viewModel.isLoading)
                    .submitLabel(.go)
                    .onSubmit {
                        Task {
                            await viewModel.analyze()
                        }
                    }
                    .onChange(of: viewModel.youtubeLink) {
                        viewModel.handleYouTubeLinkChange()
                    }

                Group {
                    if focusedField == .youtubeLink && !viewModel.youtubeLink.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                        Button {
                            viewModel.youtubeLink = ""
                            viewModel.handleYouTubeLinkChange()
                            focusedField = .youtubeLink
                        } label: {
                            Image(systemName: "xmark.circle.fill")
                                .font(.system(size: 20, weight: .semibold))
                                .foregroundStyle(.secondary)
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
            .padding(.horizontal, 20)
            .frame(height: 72)
            .background(.ultraThinMaterial, in: Capsule())
            .overlay {
                Capsule()
                    .strokeBorder(.white.opacity(0.35), lineWidth: 1)
            }
            .shadow(color: .black.opacity(0.08), radius: 20, y: 10)
            .contentShape(Capsule())
            .onTapGesture {
                focusedField = .youtubeLink
            }

            if focusedField == .youtubeLink {
                Button {
                    focusedField = nil
                } label: {
                    Image(systemName: "xmark")
                        .font(.system(size: 28, weight: .medium))
                        .foregroundStyle(.primary)
                        .frame(width: 72, height: 72)
                        .background(.ultraThinMaterial, in: Circle())
                        .overlay {
                            Circle()
                                .strokeBorder(.white.opacity(0.35), lineWidth: 1)
                        }
                        .shadow(color: .black.opacity(0.08), radius: 20, y: 10)
                }
                .buttonStyle(.plain)
            }
        }
    }
}

private struct PillFlowLayout: Layout {
    var itemSpacing: CGFloat
    var rowSpacing: CGFloat

    init(itemSpacing: CGFloat = 12, rowSpacing: CGFloat = 12) {
        self.itemSpacing = itemSpacing
        self.rowSpacing = rowSpacing
    }

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let containerWidth = proposal.width ?? .greatestFiniteMagnitude
        var currentRowWidth: CGFloat = 0
        var currentRowHeight: CGFloat = 0
        var totalHeight: CGFloat = 0
        var maxWidth: CGFloat = 0

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            let proposedRowWidth = currentRowWidth == 0 ? size.width : currentRowWidth + itemSpacing + size.width

            if proposedRowWidth > containerWidth, currentRowWidth > 0 {
                totalHeight += currentRowHeight + rowSpacing
                maxWidth = max(maxWidth, currentRowWidth)
                currentRowWidth = size.width
                currentRowHeight = size.height
            } else {
                currentRowWidth = proposedRowWidth
                currentRowHeight = max(currentRowHeight, size.height)
            }
        }

        totalHeight += currentRowHeight
        maxWidth = max(maxWidth, currentRowWidth)
        return CGSize(width: maxWidth, height: totalHeight)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var currentX = bounds.minX
        var currentY = bounds.minY
        var rowHeight: CGFloat = 0

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            let exceedsRow = currentX > bounds.minX && currentX + size.width > bounds.maxX

            if exceedsRow {
                currentX = bounds.minX
                currentY += rowHeight + rowSpacing
                rowHeight = 0
            }

            subview.place(
                at: CGPoint(x: currentX, y: currentY),
                proposal: ProposedViewSize(width: size.width, height: size.height)
            )

            currentX += size.width + itemSpacing
            rowHeight = max(rowHeight, size.height)
        }
    }
}

@MainActor
private final class KeyboardObserver: ObservableObject {
    @Published private(set) var visibleHeight: CGFloat = 0
    @Published private(set) var animationDuration: Double = 0.25

    private var cancellables = Set<AnyCancellable>()

    init(notificationCenter: NotificationCenter = .default) {
        notificationCenter.publisher(for: UIResponder.keyboardWillChangeFrameNotification)
            .merge(with: notificationCenter.publisher(for: UIResponder.keyboardWillHideNotification))
            .sink { [weak self] notification in
                self?.handleKeyboardNotification(notification)
            }
            .store(in: &cancellables)
    }

    private func handleKeyboardNotification(_ notification: Notification) {
        guard let userInfo = notification.userInfo else { return }

        if let duration = userInfo[UIResponder.keyboardAnimationDurationUserInfoKey] as? Double {
            animationDuration = duration
        }

        guard let endFrame = userInfo[UIResponder.keyboardFrameEndUserInfoKey] as? CGRect else {
            visibleHeight = 0
            return
        }

        let screenHeight = UIScreen.main.bounds.height
        visibleHeight = max(0, screenHeight - endFrame.minY)
    }
}

