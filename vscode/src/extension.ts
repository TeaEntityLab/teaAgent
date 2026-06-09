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

    const disposableDaily = vscode.commands.registerCommand('teaagent.agentDaily', async () => {
        const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '.';
        const provider = vscode.workspace.getConfiguration('teaagent').get<string>('defaultProvider', 'gpt');
        const permMode = vscode.workspace.getConfiguration('teaagent').get<string>('defaultPermissionMode', 'prompt');
        const task = await promptForInput('Enter daily task (optional)', 'Daily readiness check');

        const args = ['agent', 'daily', provider];
        if (task) {
            args.push(task);
        }
        args.push('--permission-mode', permMode);

        await runTeaAgentWithOutput(args, { title: 'Running Daily Brief', cwd: workspaceRoot });
    });

    const disposableStatus = vscode.commands.registerCommand('teaagent.agentStatus', async () => {
        const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '.';
        const runId = await promptForInput('Enter run id');
        if (!runId) {
            return;
        }

        await runTeaAgentWithOutput(['agent', 'status', runId], { title: 'Run Status', cwd: workspaceRoot });
    });

    const disposableResume = vscode.commands.registerCommand('teaagent.agentResume', async () => {
        const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '.';
        const runId = await promptForInput('Enter run id to resume');
        if (!runId) {
            return;
        }

        runTeaAgent(['agent', 'resume', runId], workspaceRoot);
    });

    const disposableAttach = vscode.commands.registerCommand('teaagent.agentAttach', async () => {
        const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '.';
        const runId = await promptForInput('Enter run id to attach');
        if (!runId) {
            return;
        }

        runTeaAgent(['agent', 'attach', runId, '--follow'], workspaceRoot);
    });

    const disposablePlan = vscode.commands.registerCommand('teaagent.agentPlan', async () => {
        const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '.';
        const provider = vscode.workspace.getConfiguration('teaagent').get<string>('defaultProvider', 'gpt');
        const task = await promptForInput('Enter task to plan');
        if (!task) {
            return;
        }

        await runTeaAgentWithOutput(
            ['agent', 'plan', provider, task, '--permission-mode', 'read-only'],
            { title: 'Creating Plan', cwd: workspaceRoot }
        );
    });

    const disposableEvidence = vscode.commands.registerCommand('teaagent.agentEvidence', async () => {
        const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '.';
        const runId = await promptForInput('Enter run id for evidence summary');
        if (!runId) {
            return;
        }

        await runTeaAgentWithOutput(
            ['agent', 'status', runId, '--evidence', '--human'],
            { title: 'Run Evidence', cwd: workspaceRoot }
        );
    });

    const disposableUndo = vscode.commands.registerCommand('teaagent.agentUndo', async () => {
        const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '.';
        const runId = await promptForInput('Enter run id to undo (empty = last run with journal)');
        const args = ['agent', 'undo'];
        if (runId) {
            args.push(runId);
        } else {
            args.push('--last');
        }

        await runTeaAgentWithOutput(args, { title: 'Undo Run Changes', cwd: workspaceRoot });
    });

    const disposableApprovalPending = vscode.commands.registerCommand('teaagent.agentApprovalPending', async () => {
        const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '.';
        await runTeaAgentWithOutput(
            ['approval', 'pending', '--human'],
            { title: 'Pending Approvals', cwd: workspaceRoot }
        );
    });

    const disposableApprovalApprove = vscode.commands.registerCommand('teaagent.agentApprovalApprove', async () => {
        const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '.';
        const selector = await promptForInput(
            'Enter pending action number from approval pending list'
        );
        if (!selector) {
            return;
        }

        runTeaAgent(
            ['approval', 'approve', '--selector', selector, '--resume'],
            workspaceRoot
        );
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
        disposableDaily,
        disposableStatus,
        disposableResume,
        disposableAttach,
        disposablePlan,
        disposableEvidence,
        disposableUndo,
        disposableApprovalPending,
        disposableApprovalApprove,
        disposablePreflight,
        disposableProviders,
        disposableGQLSmoke,
        disposableMcpServer,
        disposableTUI,
        taskProvider
    );
}

export function deactivate(): void {}
