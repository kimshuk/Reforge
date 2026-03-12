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
    @FocusState private var focusedField: Field?

    init(viewModel: HomeViewModel) {
        _viewModel = StateObject(wrappedValue: viewModel)
    }
    
    var body: some View {
        GeometryReader { geometry in
            ZStack(alignment: .bottom) {
                Color.clear
                    .contentShape(Rectangle())
                    .onTapGesture {
                        focusedField = nil
                    }

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
                                .frame(maxWidth: .infinity)
                                .aspectRatio(16 / 9, contentMode: .fit)
                                .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                            }
                        }
                    }

                    if !viewModel.errorMessage.isEmpty {
                        Text(viewModel.errorMessage)
                            .font(.footnote)
                            .foregroundStyle(.red)
                    }

                    if viewModel.youtubeLink.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                        Spacer()

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

                        Spacer()
                    } else {
                        Spacer()
                    }

                }
                .padding()
                .safeAreaInset(edge: .bottom) {
                    Color.clear.frame(height: 88)
                }
                .ignoresSafeArea(.keyboard)

                bottomFloatingBar
                    .padding(.horizontal, 16)
                    .padding(.bottom, bottomBarPadding(in: geometry))
                    .animation(.easeOut(duration: keyboardObserver.animationDuration), value: keyboardObserver.visibleHeight)
            }
        }
        .navigationDestination(item: $viewModel.analysisResult) { result in
            AnalyzeResultView(result: result)
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

    private var bottomFloatingBar: some View {
        HStack(spacing: 14) {
            HStack(spacing: 12) {
                TextField("Paste YouTube URL", text: $viewModel.youtubeLink)
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
