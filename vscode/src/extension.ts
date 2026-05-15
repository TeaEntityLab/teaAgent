import * as vscode from 'vscode';
import * as cp from 'child_process';

function executablePath(): string {
    return vscode.workspace.getConfiguration('teaagent').get<string>('executablePath', 'teaagent');
}

function runTeaAgent(args: string[], cwd?: string): void {
    const exe = executablePath();
    const workspaceRoot = cwd || vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '.';

    const terminal = vscode.window.createTerminal({
        name: 'TeaAgent',
        cwd: workspaceRoot
    });
    terminal.show();
    terminal.sendText([exe, ...args].join(' '));
}

function runTeaAgentWithOutput(
    args: string[],
    options: { title: string; cwd?: string }
): Thenable<void> {
    const exe = executablePath();
    const workspaceRoot = options.cwd || vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '.';

    return vscode.window.withProgress(
        {
            location: vscode.ProgressLocation.Notification,
            title: options.title,
            cancellable: false
        },
        (_progress) => {
            return new Promise<void>((resolve) => {
                const child = cp.spawn(exe, args, {
                    cwd: workspaceRoot,
                    env: { ...process.env }
                });

                let stdout = '';
                let stderr = '';

                child.stdout.on('data', (data: Buffer) => {
                    stdout += data.toString();
                });

                child.stderr.on('data', (data: Buffer) => {
                    stderr += data.toString();
                });

                child.on('close', (code: number | null) => {
                    const channel = vscode.window.createOutputChannel('TeaAgent', { log: true });
                    channel.clear();
                    if (stdout) {
                        channel.appendLine(stdout);
                    }
                    if (stderr) {
                        channel.appendLine(stderr);
                    }
                    if (code !== 0) {
                        channel.appendLine(`\nExited with code ${code}`);
                        vscode.window.showWarningMessage(`TeaAgent ${options.title} exited with code ${code}`);
                    } else {
                        vscode.window.showInformationMessage(`TeaAgent ${options.title} completed`);
                    }
                    resolve();
                });
            });
        }
    );
}

async function promptForInput(prompt: string, placeHolder?: string): Promise<string | undefined> {
    return vscode.window.showInputBox({
        prompt,
        placeHolder,
        ignoreFocusOut: true
    });
}

export function activate(context: vscode.ExtensionContext): void {
    const disposableDoctor = vscode.commands.registerCommand('teaagent.doctor', async () => {
        await runTeaAgentWithOutput(['doctor', 'all'], { title: 'Running Doctor' });
    });

    const disposableAgentRun = vscode.commands.registerCommand('teaagent.agentRun', async () => {
        const provider = vscode.workspace.getConfiguration('teaagent').get<string>('defaultProvider', 'gpt');
        const model = vscode.workspace.getConfiguration('teaagent').get<string>('defaultModel', '');
        const permMode = vscode.workspace.getConfiguration('teaagent').get<string>('defaultPermissionMode', 'prompt');

        const task = await promptForInput('Enter the agent task');
        if (!task) {
            return;
        }

        const args = ['agent', 'run', provider, task, '--permission-mode', permMode];
        if (model) {
            args.push('--model', model);
        }

        const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '.';
        runTeaAgent(args, workspaceRoot);
    });

    const disposablePreflight = vscode.commands.registerCommand('teaagent.agentPreflight', async () => {
        const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '.';
        const provider = vscode.workspace.getConfiguration('teaagent').get<string>('defaultProvider', 'gpt');
        const task = await promptForInput('Enter preflight task', 'Summarize repository status');
        if (!task) {
            return;
        }

        await runTeaAgentWithOutput(
            ['agent', 'preflight', provider, task],
            { title: 'Running Preflight', cwd: workspaceRoot }
        );
    });

    const disposableMcpServer = vscode.commands.registerCommand('teaagent.startMcpServer', async () => {
        const port = vscode.workspace.getConfiguration('teaagent').get<number>('mcpServerPort', 7330);
        const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '.';
        runTeaAgent(['mcp', 'serve', '--http', '--port', String(port), '--root', workspaceRoot], workspaceRoot);
    });

    const disposableProviders = vscode.commands.registerCommand('teaagent.modelProviders', async () => {
        await runTeaAgentWithOutput(['model', 'providers'], { title: 'Listing Model Providers' });
    });

    const disposableGQLSmoke = vscode.commands.registerCommand('teaagent.graphqliteSmoke', async () => {
        const dbPath = vscode.workspace.getConfiguration('teaagent').get<string>('databasePath', ':memory:');
        await runTeaAgentWithOutput(
            ['graphqlite', 'smoke', '--database', dbPath],
            { title: 'Running GraphQLite Smoke Test' }
        );
    });

    const disposableTUI = vscode.commands.registerCommand('teaagent.openTUI', () => {
        const exe = executablePath();
        const terminal = vscode.window.createTerminal({
            name: 'TeaAgent TUI',
            cwd: vscode.workspace.workspaceFolders?.[0]?.uri.fsPath
        });
        terminal.show();
        terminal.sendText(exe + ' tui');
    });

    const taskProvider = vscode.tasks.registerTaskProvider('teaagent', {
        provideTasks: (): vscode.ProviderResult<vscode.Task[]> => {
            const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '.';

            const doctorTask = new vscode.Task(
                { type: 'teaagent', command: 'doctor all' },
                vscode.TaskScope.Workspace,
                'Doctor Check',
                'teaagent',
                new vscode.ShellExecution(executablePath() + ' doctor all', { cwd: workspaceRoot })
            );

            const preflightTask = new vscode.Task(
                { type: 'teaagent', command: 'agent preflight' },
                vscode.TaskScope.Workspace,
                'Agent Preflight',
                'teaagent',
                new vscode.ShellExecution(executablePath() + ' agent preflight', { cwd: workspaceRoot })
            );

            return [doctorTask, preflightTask];
        },
        resolveTask: (
            _task: vscode.Task
        ): vscode.ProviderResult<vscode.Task> => {
            return undefined;
        }
    });

    context.subscriptions.push(
        disposableDoctor,
        disposableAgentRun,
        disposablePreflight,
        disposableProviders,
        disposableGQLSmoke,
        disposableMcpServer,
        disposableTUI,
        taskProvider
    );
}

export function deactivate(): void {}
