import { useCallback, useEffect, useMemo, useState } from 'react'
import { getNetworkStatus, getTransfers } from '../api/client'
import DispatchModal from '../components/admin/DispatchModal'
import KpiCards from '../components/admin/KpiCards'
import TelemetryTable from '../components/admin/TelemetryTable'
import TransfersPanel from '../components/admin/TransfersPanel'
import { flatten, type Row } from '../components/admin/rows'
import { usePolling } from '../hooks/usePolling'
import VoiceReportBox from '../components/admin/VoiceReportBox'
import './AdminPage.scss'

const fetchTransfers = () => getTransfers(20)

type AdminSection = 'dashboard' | 'operations'

export default function AdminPage() {
  const net = usePolling(getNetworkStatus, 15_000)
  const tr = usePolling(fetchTransfers, 15_000)

  const rows = useMemo(() => flatten(net.data), [net.data])

  const [dispatchRow, setDispatchRow] = useState<Row | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [activeSection, setActiveSection] =
    useState<AdminSection>('dashboard')

  useEffect(() => {
    if (!toast) return

    const id = setTimeout(() => setToast(null), 4000)

    return () => clearTimeout(id)
  }, [toast])

  const refreshAll = useCallback(() => {
    void net.refresh()
    void tr.refresh()
  }, [net.refresh, tr.refresh])

  const closeModal = useCallback(() => {
    setDispatchRow(null)
  }, [])

  return (
    <div className="admin-page">
      <div className="admin-container">

        {/* =====================================================
            HEADER
        ====================================================== */}
        <header className="admin-header">

          <div className="admin-title-section">
            <div className="admin-title-icon">
              <span>⌘</span>
            </div>

            <div>
              <div className="admin-eyebrow">
                <span className="status-dot" />
                LIVE OPERATIONS
              </div>

              <h1 className="admin-title">
                Admin command center
              </h1>

              <p className="admin-subtitle">
                Monitor healthcare infrastructure, resources and
                patient transfers.
              </p>
            </div>
          </div>

          <button
            type="button"
            className="admin-refresh-btn"
            onClick={refreshAll}
          >
            <span className="refresh-icon">↻</span>
            Refresh
          </button>
        </header>

        {/* =====================================================
            ERROR
        ====================================================== */}
        {net.error && (
          <div className="admin-error" role="alert">
            <div className="admin-error-content">

              <div className="admin-error-icon">
                !
              </div>

              <div>
                <strong>Unable to load network data</strong>
                <p>{net.error}</p>
              </div>

            </div>

            <button
              type="button"
              className="admin-retry-btn"
              onClick={() => void net.refresh()}
            >
              Retry
            </button>
          </div>
        )}

        {/* =====================================================
            PAGE NAVIGATION
        ====================================================== */}
        <nav
          className="admin-tabs"
          aria-label="Admin sections"
        >
          <button
            type="button"
            className={`admin-tab ${
              activeSection === 'dashboard'
                ? 'active'
                : ''
            }`}
            onClick={() => setActiveSection('dashboard')}
          >
            <span className="admin-tab-icon">▣</span>

            <span>
              <strong>Dashboard</strong>
              <small>Network overview</small>
            </span>
          </button>

          <button
            type="button"
            className={`admin-tab ${
              activeSection === 'operations'
                ? 'active'
                : ''
            }`}
            onClick={() => setActiveSection('operations')}
          >
            <span className="admin-tab-icon">⚡</span>

            <span>
              <strong>Operations</strong>
              <small>Reports &amp; transfers</small>
            </span>
          </button>
        </nav>

        {/* =====================================================
            DASHBOARD
        ====================================================== */}
        {activeSection === 'dashboard' && (
          <main className="admin-content">

            {/* Network overview */}
            <section className="admin-section">

              <div className="section-heading">
                <div>
                  <span className="section-kicker">
                    NETWORK OVERVIEW
                  </span>

                  <h2>
                    Healthcare network
                  </h2>
                </div>

                <span className="live-indicator">
                  <span className="status-dot" />
                  Updating automatically
                </span>
              </div>

              <div className="kpi-wrapper">
                <KpiCards
                  data={net.data}
                  loading={net.loading}
                />
              </div>

            </section>

            {/* PHC telemetry */}
            <section className="admin-section">

              <div className="section-heading">
                <div>
                  <span className="section-kicker">
                    FACILITY MONITORING
                  </span>

                  <h2>
                    PHC telemetry
                  </h2>
                </div>

                <span className="record-count">
                  {rows.length}{' '}
                  {rows.length === 1
                    ? 'facility'
                    : 'facilities'}
                </span>
              </div>

              <div className="admin-panel telemetry-panel">
                <TelemetryTable
                  rows={rows}
                  onDispatch={setDispatchRow}
                />
              </div>

            </section>

          </main>
        )}

        {/* =====================================================
            OPERATIONS
        ====================================================== */}
        {activeSection === 'operations' && (
          <main className="admin-content">

            <section className="admin-section">

              <div className="section-heading">
                <div>
                  <span className="section-kicker">
                    OPERATIONS
                  </span>

                  <h2>
                    Dispatch &amp; transfers
                  </h2>

                  <p className="section-description">
                    Manage facility reports and monitor
                    patient transfers across the network.
                  </p>
                </div>

                <span className="operations-status">
                  <span className="status-dot" />
                  Operations active
                </span>
              </div>

              <div className="row g-4">

                {/* Voice reports */}
                <div className="col-12 col-lg-6">
                  <div className="admin-panel admin-operation-panel">

                    <div className="panel-header">

                      <div className="panel-icon voice-icon">
                        🎙
                      </div>

                      <div>
                        <h3>
                          Voice reports
                        </h3>

                        <p>
                          Submit and apply facility
                          updates using voice.
                        </p>
                      </div>

                    </div>

                    <VoiceReportBox
                      phcs={net.data?.phcs ?? []}
                      onApplied={refreshAll}
                    />

                  </div>
                </div>

                {/* Patient transfers */}
                <div className="col-12 col-lg-6">
                  <div className="admin-panel admin-operation-panel">

                    <div className="panel-header">

                      <div className="panel-icon transfer-icon">
                        ⇄
                      </div>

                      <div>
                        <h3>
                          Patient transfers
                        </h3>

                        <p>
                          Monitor recent transfer
                          activity.
                        </p>
                      </div>

                    </div>

                    <TransfersPanel
                      transfers={tr.data}
                      error={tr.error}
                      loading={tr.loading}
                    />

                  </div>
                </div>

              </div>

            </section>

          </main>
        )}

        {/* =====================================================
            FOOTER
        ====================================================== */}
        <div className="admin-footer">

          <div>
            <span className="footer-status-dot" />
            System monitoring active
          </div>

          <span>
            Data refreshes every 15 seconds
          </span>

        </div>

      </div>

      {/* =======================================================
          DISPATCH MODAL
      ======================================================== */}
      {dispatchRow && (
        <DispatchModal
          key={dispatchRow.key}
          row={dispatchRow}
          onClose={closeModal}
          onRecorded={refreshAll}
          onApproved={() => {
            setToast('Dispatch recorded')
            closeModal()
          }}
        />
      )}

      {/* =======================================================
          SUCCESS TOAST
      ======================================================== */}
      {toast && (
        <div className="admin-toast-container">

          <div
            className="admin-toast"
            role="status"
          >

            <div className="toast-success-icon">
              ✓
            </div>

            <div className="toast-message">
              <strong>Success</strong>
              <span>{toast}</span>
            </div>

            <button
              type="button"
              className="toast-close"
              aria-label="Close"
              onClick={() => setToast(null)}
            >
              ×
            </button>

          </div>

        </div>
      )}

    </div>
  )
}