//
//  HomeView.swift
//  NoteApp
//
//  Created by 김지수 on 3/7/26.
//

import SwiftUI

struct HomeView: View {
    @StateObject private var viewModel: HomeViewModel
    @State private var isEditingTitle = false
    @State private var editingTitle = ""

    init(viewModel: HomeViewModel) {
        _viewModel = StateObject(wrappedValue: viewModel)
    }
    
    var body: some View {
        ZStack(alignment: .bottom) {
            VStack(alignment: .leading, spacing: 16) {
                Text("Analyze YouTube Video")
                    .font(.title2.bold())
                
                if viewModel.shouldShowTitleArea {
                    VStack(alignment: .leading) {
                        Text("Video title")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        HStack {
                            if isEditingTitle {
                                TextField("Video title", text: $editingTitle)
                                    .textInputAutocapitalization(.sentences)
                                    .autocorrectionDisabled(false)
                                    .padding(12)
                                    .background(Color(.systemGray6))
                                    .clipShape(RoundedRectangle(cornerRadius: 10))
                            } else {
                                Text(viewModel.titleDisplayText)
                                    .font(.body)
                                    .padding(12)
                                    .background(Color(.systemGray6))
                                    .clipShape(RoundedRectangle(cornerRadius: 10))
                            }
                            Spacer()
                            if isEditingTitle {
                                HStack(spacing: 8) {
                                    Button("Cancel") {
                                        editingTitle = viewModel.titleInput
                                        isEditingTitle = false
                                    }
                                    .buttonStyle(.bordered)

                                    Button("Save") {
                                        viewModel.titleInput = editingTitle.trimmingCharacters(in: .whitespacesAndNewlines)
                                        isEditingTitle = false
                                    }
                                    .buttonStyle(.borderedProminent)
                                }
                            } else {
                                Button("Edit") {
                                    editingTitle = viewModel.titleInput
                                    isEditingTitle = true
                                }
                                .buttonStyle(.bordered)
                            }
                        }
                    }
                }

                if !viewModel.errorMessage.isEmpty {
                    Text(viewModel.errorMessage)
                        .font(.footnote)
                        .foregroundStyle(.red)
                }

                Spacer()
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
        .onChange(of: viewModel.shouldShowTitleArea) {
            if !viewModel.shouldShowTitleArea {
                isEditingTitle = false
                editingTitle = ""
            }
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
                    .onChange(of: viewModel.youtubeLink) {
                        viewModel.handleYouTubeLinkChange()
                    }

                Group {
                    if !viewModel.youtubeLink.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                        Button {
                            viewModel.youtubeLink = ""
                            viewModel.handleYouTubeLinkChange()
                        } label: {
                            Image(systemName: "xmark.circle.fill")
                                .font(.system(size: 20, weight: .semibold))
                                .foregroundStyle(.secondary)
                        }
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

            Button {
                Task {
                    await viewModel.analyze()
                }
            } label: {
                ZStack {
                    if viewModel.isLoading {
                        ProgressView()
                            .progressViewStyle(.circular)
                            .tint(.primary)
                    } else {
                        Image(systemName: "square.and.pencil")
                            .font(.system(size: 28, weight: .medium))
                            .foregroundStyle(.primary)
                    }
                }
                .frame(width: 72, height: 72)
                .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 28, style: .continuous))
                .overlay {
                    RoundedRectangle(cornerRadius: 28, style: .continuous)
                        .strokeBorder(.white.opacity(0.35), lineWidth: 1)
                }
                .shadow(color: .black.opacity(0.08), radius: 20, y: 10)
            }
            .disabled(viewModel.isLoading || viewModel.videoUnavailableReason != nil)
        }
    }
}
