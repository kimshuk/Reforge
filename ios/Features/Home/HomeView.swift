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

            HStack(spacing: 8) {
                TextField("https://www.youtube.com/watch?v=...", text: $viewModel.youtubeLink)
                    .textInputAutocapitalization(.never)
                    .keyboardType(.URL)
                    .autocorrectionDisabled()
                    .padding(12)
                    .background(Color(.systemGray6))
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                    .onChange(of: viewModel.youtubeLink) {
                        viewModel.handleYouTubeLinkChange()
                    }

                Button("Reset") {
                    viewModel.youtubeLink = ""
                    viewModel.handleYouTubeLinkChange()
                }
                .buttonStyle(.bordered)
            }

            Button {
                Task {
                    await viewModel.analyze()
                }
            } label: {
                HStack {
                    if viewModel.isLoading {
                        ProgressView()
                            .progressViewStyle(.circular)
                    }
                    Text(viewModel.isLoading ? "Analyzing..." : "Analyze")
                }
            }
            .buttonStyle(.borderedProminent)
            .disabled(viewModel.isLoading || viewModel.videoUnavailableReason != nil)

            if !viewModel.errorMessage.isEmpty {
                Text(viewModel.errorMessage)
                    .font(.footnote)
                    .foregroundStyle(.red)
            }

            Spacer()
        }
        .padding()
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
}
