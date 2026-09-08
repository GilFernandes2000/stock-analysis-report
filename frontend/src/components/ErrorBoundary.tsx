import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/** Catches render errors — notably a failed lazy-route chunk load (offline) —
 *  so the app shows a retry instead of a blank screen or a stuck spinner. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="mx-auto max-w-md p-8 text-center">
        <p className="text-sm font-medium text-ink">This section failed to load.</p>
        <p className="mt-1 text-xs text-muted">
          Check your connection, then reload.
        </p>
        <button
          onClick={() => {
            this.setState({ error: null });
            window.location.reload();
          }}
          className="mt-4 rounded-lg border border-edge px-3 py-1.5 text-sm text-ink2 hover:border-accent/50 hover:text-ink"
        >
          Reload
        </button>
      </div>
    );
  }
}
