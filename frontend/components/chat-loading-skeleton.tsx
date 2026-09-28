import { TerminalTelemetry } from "@/components/terminal-telemetry"

export function ChatLoadingSkeleton() {
  return (
    <div className="slsg-chat-workspace slsg-chat-loading">
      <div className="sr-only" role="status">
        チャットを読み込んでいます…
      </div>
      <div aria-hidden="true" className="slsg-chat-loading-content">
        <header className="slsg-chat-header">
          <div className="slsg-chat-panel-header">
            <span className="slsg-chat-loading-line is-panel-title" />
            <span className="slsg-chat-loading-line is-panel-detail" />
            <span className="slsg-chat-loading-button" />
          </div>
        </header>

        <div className="slsg-chat-layout">
          <div className="slsg-chat-conversation">
            <div className="slsg-chat-conversation-inner">
              <div className="slsg-chat-panel-body">
                <div className="slsg-chat-message-list slsg-chat-loading-messages">
                  <div className="slsg-chat-loading-message">
                    <span className="slsg-chat-loading-avatar" />
                    <div className="slsg-chat-loading-message-lines">
                      <span className="slsg-chat-loading-line is-message-title" />
                      <span className="slsg-chat-loading-line is-message-body" />
                    </div>
                  </div>
                </div>
                <div className="slsg-chat-composer slsg-chat-loading-composer">
                  <span className="slsg-chat-loading-line is-input" />
                  <span className="slsg-chat-loading-button" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <TerminalTelemetry />
    </div>
  )
}
