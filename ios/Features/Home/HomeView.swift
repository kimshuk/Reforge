//
//  HomeView.swift
//  NoteApp
//
//  Created by 김지수 on 3/7/26.
//

import SwiftUI

struct HomeView: View {
    private enum Field: Hashable {
        case title
        case youtubeLink
    }

    @StateObject private var viewModel: HomeViewModel
    @FocusState private var focusedField: Field?

    init(viewModel: HomeViewModel) {
        _viewModel = StateObject(wrappedValue: viewModel)
    }
    
    var body: some View {
        ZStack(alignment: .bottom) {
            Color.clear
                .contentShape(Rectangle())
                .onTapGesture {
                    focusedField = nil
                }

            VStack(alignment: .leading, spacing: 16) {                
                if viewModel.shouldShowTitleArea {
                    VStack(alignment: .leading) {
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

            bottomFloatingBar
                .padding(.horizontal, 16)
                .padding(.bottom, 12)
        }
        .navigationDestination(item: $viewModel.analysisResult) { result in
            AnalyzeResultView(result: result)
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
