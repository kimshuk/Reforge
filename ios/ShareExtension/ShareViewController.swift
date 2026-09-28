import Combine
import UIKit

@MainActor
final class ShareViewController: UIViewController {
    private let statusLabel = UILabel()
    private let spinner = UIActivityIndicatorView(style: .medium)
    private let restoreActions = UIStackView()
    private var ingestionTask: Task<Void, Never>?
    private var restoreTask: Task<Void, Never>?
    private var viewModel: ShareExtensionViewModel?
    private var cancellables = Set<AnyCancellable>()

    override func viewDidLoad() {
        super.viewDidLoad()
        configureView()
        ingestionTask = Task { [weak self] in
            await self?.run()
        }
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        ingestionTask?.cancel()
        restoreTask?.cancel()
    }

    deinit {
        ingestionTask?.cancel()
        restoreTask?.cancel()
    }

    private func configureView() {
        view.backgroundColor = .systemBackground
        statusLabel.numberOfLines = 0
        statusLabel.textAlignment = .center
        statusLabel.translatesAutoresizingMaskIntoConstraints = false
        spinner.translatesAutoresizingMaskIntoConstraints = false
        spinner.startAnimating()
        let cancelButton = UIButton(type: .system)
        cancelButton.setTitle("Cancel", for: .normal)
        cancelButton.addTarget(self, action: #selector(cancelRestore), for: .touchUpInside)
        let restoreButton = UIButton(type: .system)
        restoreButton.setTitle("Restore", for: .normal)
        restoreButton.addTarget(self, action: #selector(confirmRestore), for: .touchUpInside)
        restoreActions.axis = .horizontal
        restoreActions.distribution = .fillEqually
        restoreActions.spacing = 24
        restoreActions.translatesAutoresizingMaskIntoConstraints = false
        restoreActions.isHidden = true
        restoreActions.addArrangedSubview(cancelButton)
        restoreActions.addArrangedSubview(restoreButton)
        view.addSubview(statusLabel)
        view.addSubview(spinner)
        view.addSubview(restoreActions)
        NSLayoutConstraint.activate([
            spinner.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            spinner.centerYAnchor.constraint(equalTo: view.centerYAnchor, constant: -20),
            statusLabel.topAnchor.constraint(equalTo: spinner.bottomAnchor, constant: 16),
            statusLabel.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 24),
            statusLabel.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -24),
            restoreActions.topAnchor.constraint(equalTo: statusLabel.bottomAnchor, constant: 24),
            restoreActions.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 24),
            restoreActions.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -24),
        ])
    }

    private func run() async {
        guard let context = extensionContext else { return }
        do {
            let input = try await ShareInputLoader().load(
                from: context.inputItems.compactMap { $0 as? NSExtensionItem }
            )
            let container = try SharedModelContainer.makeAppGroupContainer()
            let repository = ContentNoteRepository(
                container: container,
                lock: try SharedModelContainer.appGroupLock()
            )
            guard let baseURL = URL(string: AppConfig.default.backendBaseURL) else {
                throw ShareInputLoaderError.invalidInput
            }
            let coordinator = ShareIngestionCoordinator(
                repository: repository,
                transcriptService: URLSessionYouTubeTranscriptService(baseURL: baseURL)
            )
            let viewModel = ShareExtensionViewModel(
                ingestor: coordinator,
                complete: { [weak context] in
                    context?.completeRequest(returningItems: nil)
                },
                cancel: { [weak context] in
                    context?.cancelRequest(withError: CancellationError())
                }
            )
            self.viewModel = viewModel
            bind(viewModel)
            await viewModel.run(input: input)
        } catch {
            context.cancelRequest(withError: error)
        }
    }

    private func bind(_ viewModel: ShareExtensionViewModel) {
        viewModel.$phase
            .sink { [weak self] phase in
                if case .awaitingRestore = phase {
                    self?.restoreActions.isHidden = false
                } else {
                    self?.restoreActions.isHidden = true
                }
            }
            .store(in: &cancellables)
        viewModel.$statusText
            .sink { [weak self] text in self?.statusLabel.text = text }
            .store(in: &cancellables)
        viewModel.$isLoading
            .sink { [weak self] isLoading in
                if isLoading {
                    self?.spinner.startAnimating()
                } else {
                    self?.spinner.stopAnimating()
                }
            }
            .store(in: &cancellables)
    }

    @objc private func cancelRestore() {
        restoreTask?.cancel()
        restoreTask = nil
        viewModel?.cancelRestore()
    }

    @objc private func confirmRestore() {
        guard restoreTask == nil, let viewModel else { return }
        guard case .awaitingRestore = viewModel.phase else { return }
        restoreTask = Task { [weak self] in
            await viewModel.confirmRestore()
            self?.restoreTask = nil
        }
    }
}
