import React, { useState, useEffect } from 'react';
import { 
  GraduationCap, Sun, Moon, User, AlertTriangle, BookOpen, Calendar, Sliders, Activity, 
  Database, CheckCircle, XCircle, Info, ChevronRight, ArrowRight,
  TrendingUp, ShieldAlert, Award, FileText, Check, AlertCircle
} from 'lucide-react';

export default function App() {
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('ntu_dss_theme') || 'light';
  });

  const [scenarios, setScenarios] = useState([]);
  const [selectedStudent, setSelectedStudent] = useState('V2-001');
  const [currentTab, setCurrentTab] = useState(0);
  const [dssData, setDssData] = useState(null);
  const [dagData, setDagData] = useState(null);
  const [simData, setSimData] = useState(null);
  const [loading, setLoading] = useState(true);

  // What-if sliders state
  const [wiLambda, setWiLambda] = useState(0.1);
  const [wiBeta, setWiBeta] = useState(0.125);
  const [wiGamma, setWiGamma] = useState(1.0);
  const [wiRiskMode, setWiRiskMode] = useState('soft');
  const [wiOverride, setWiOverride] = useState({});
  const [whatIfResult, setWhatIfResult] = useState(null);
  const [simLambda, setSimLambda] = useState(0.1);

  // Theme effect
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('ntu_dss_theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light');
  };

  // Fetch scenarios on load
  useEffect(() => {
    fetch('/api/scenarios')
      .then(res => res.json())
      .then(data => {
        setScenarios(data);
        if (data.length > 0) setSelectedStudent(data[0].student_id);
      })
      .catch(err => console.error("Error loading scenarios:", err));
  }, []);

  // Fetch DSS & DAG data when student changes
  useEffect(() => {
    if (!selectedStudent) return;
    setLoading(true);

    Promise.all([
      fetch(`/api/dss/${selectedStudent}?lambda=${wiLambda}&beta=${wiBeta}&gamma=${wiGamma}`).then(res => res.json()),
      fetch(`/api/dag/${selectedStudent}`).then(res => res.json()),
      fetch(`/api/simulation/${selectedStudent}?lambda=${simLambda}`).then(res => res.json()),
    ])
    .then(([dss, dag, sim]) => {
      setDssData(dss);
      setDagData(dag);
      setSimData(sim);
      setWhatIfResult(null); // Reset whatif
      setLoading(false);
    })
    .catch(err => {
      console.error("Error loading student data:", err);
      setLoading(false);
    });
  }, [selectedStudent]);

  // Handle What-if evaluation
  const runWhatIf = () => {
    fetch(`/api/dss/${selectedStudent}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        load_lambda: wiLambda,
        beta: wiBeta,
        gamma: wiGamma,
        risk_cap_mode: wiRiskMode,
        progress_override: wiOverride
      })
    })
    .then(res => res.json())
    .then(data => setWhatIfResult(data))
    .catch(err => console.error("Whatif calculation error:", err));
  };

  // Re-fetch simulation on simLambda change
  useEffect(() => {
    if (!selectedStudent) return;
    fetch(`/api/simulation/${selectedStudent}?lambda=${simLambda}`)
      .then(res => res.json())
      .then(sim => setSimData(sim))
      .catch(err => console.error("Simulation error:", err));
  }, [simLambda]);

  const navItems = [
    { label: "1. Hồ sơ & Tiến độ", icon: User },
    { label: "2. Nguy cơ & Giải thích XAI", icon: AlertTriangle },
    { label: "3. Học phần & Sơ đồ DAG", icon: BookOpen },
    { label: "4. Phương án Đăng ký (ILP)", icon: Calendar },
    { label: "5. Phân tích What-if", icon: Sliders },
    { label: "6. Mô phỏng Monte Carlo", icon: Activity },
    { label: "7. Dữ liệu & Giả định", icon: Database },
  ];

  const profileSummary = dssData?.profile?.summary || {};
  const stats = dssData?.profile?.stats || {};
  const creditRegime = dssData?.profile?.credit_regime || {};
  const riskData = dssData?.risk || {};
  const xaiData = riskData?.xai || {};

  const earnedCredits = stats.earned_credits || 0;
  const progressPercent = Math.min(100, Math.round((earnedCredits / 130) * 100));

  return (
    <div style={{minHeight: '100vh', display: 'flex', flexDirection: 'column'}}>
      {/* Top University Academic Header */}
      <header className="university-topbar">
        <div className="university-branding">
          <div className="university-logo-badge">
            <GraduationCap size={24} color="#FFFFFF" />
          </div>
          <div className="university-title-block">
            <h1>TRƯỜNG ĐẠI HỌC NHA TRANG · KHOA CÔNG NGHỆ THÔNG TIN</h1>
            <p>Hệ hỗ trợ quyết định Cảnh báo sớm Rủi ro học tập & Tối ưu hóa Lộ trình Tín chỉ</p>
          </div>
        </div>

        <div className="university-topbar-actions">
          <div className="academic-badge">
            <Award size={14} color="var(--edu-gold)" />
            <span>QĐ 753/QĐ-ĐHNT · Khóa 65 (2023 - 2027)</span>
          </div>

          <button 
            className="theme-toggle-btn"
            onClick={toggleTheme}
            title={`Chuyển sang ${theme === 'light' ? 'Chế độ Tối (Dark Mode)' : 'Chế độ Sáng (Light Mode)'}`}
            aria-label="Toggle theme"
          >
            {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
          </button>
        </div>
      </header>

      {/* Main Body */}
      <div className="app-container">
        {/* Sidebar */}
        <aside className="sidebar">
          <div className="sidebar-content">
            <div className="section-label">CHỌN HỒ SƠ SINH VIÊN</div>
            <select 
              className="scenario-select"
              value={selectedStudent}
              onChange={e => setSelectedStudent(e.target.value)}
            >
              {scenarios.map(s => (
                <option key={s.student_id} value={s.student_id}>
                  {s.student_id} · {s.persona}
                </option>
              ))}
            </select>

            {/* University Student ID Card */}
            <div className="student-id-card">
              <div className="student-card-header">
                <div className="student-avatar">
                  {selectedStudent.replace('V2-00', '').replace('V2-0', '')}
                </div>
                <div className="student-meta">
                  <h3>{selectedStudent} · {profileSummary.persona?.split('(')[0] || 'Sinh viên'}</h3>
                  <span>{profileSummary.specialization || 'Công nghệ Phần mềm'}</span>
                </div>
              </div>

              <div className="student-id-row">
                <span className="label">Tiến độ tích lũy:</span>
                <span className="value">{earnedCredits}/130 TC ({progressPercent}%)</span>
              </div>
              <div className="progress-track">
                <div className="progress-bar" style={{width: `${progressPercent}%`}}></div>
              </div>

              <div className="student-id-row" style={{marginTop: '10px'}}>
                <span className="label">Điểm trung bình (GPA):</span>
                <span className="value">{stats.gpa ? stats.gpa.toFixed(2) : 'N/A'}</span>
              </div>
              <div className="student-id-row">
                <span className="label">Tín chỉ nợ đọng:</span>
                <span className="value" style={{color: stats.debt_credits > 0 ? 'var(--risk-high)' : 'var(--risk-low)'}}>
                  {stats.debt_credits || 0} TC
                </span>
              </div>
              <div className="student-id-row">
                <span className="label">Chế độ QĐ 753:</span>
                <span className="value">
                  <span className="source-badge">{creditRegime.regime || 'normal'}</span>
                </span>
              </div>
              <div className="student-id-row">
                <span className="label">Học kỳ dự kiến:</span>
                <span className="value">HK {profileSummary.target_semester || 'N/A'}</span>
              </div>
            </div>

            <div className="section-label">DANH MỤC CHỨC NĂNG</div>
            <nav className="nav-menu">
              {navItems.map((item, idx) => {
                const Icon = item.icon;
                return (
                  <button
                    key={idx}
                    className={`nav-item ${currentTab === idx ? 'active' : ''}`}
                    onClick={() => setCurrentTab(idx)}
                  >
                    <Icon size={18} />
                    <span>{item.label}</span>
                  </button>
                );
              })}
            </nav>
          </div>

          <div className="sidebar-footer">
            <div style={{fontWeight: 700, color: 'var(--text-primary)'}}>Trường Đại học Nha Trang - CNTT</div>
            <div style={{marginTop: '2px', opacity: 0.8}}>Khoa Công nghệ Thông tin © 2026</div>
          </div>
        </aside>

        {/* Main Content Area */}
        <div className="main-wrapper">
          <div className="page-header-nav">
            <div className="page-header-title">
              <h2>{navItems[currentTab].label}</h2>
              <span className="badge badge-optimal">Hồ sơ: {selectedStudent}</span>
            </div>
            <div style={{fontSize: '0.82rem', color: 'var(--text-muted)'}}>
              Nguồn dữ liệu: <strong style={{color: 'var(--edu-primary)'}}>OFFICIAL (NTU) & SCENARIO</strong>
            </div>
          </div>

          <main className="main-content">
            {loading ? (
              <div style={{textAlign: 'center', padding: '60px', color: 'var(--text-muted)'}}>
                <div style={{fontSize: '1.1rem', fontWeight: 600, marginBottom: '8px'}}>Đang tải dữ liệu và tính toán mô hình...</div>
                <div style={{fontSize: '0.85rem'}}>Vui lòng đợi giây lát.</div>
              </div>
            ) : (
              <>
                {/* TAB 0: Hồ sơ & Tiến độ */}
                {currentTab === 0 && (
                  <div>
                    <div className="kpi-grid">
                      <div className="kpi-card">
                        <div className="kpi-label">Tín chỉ hoàn thành</div>
                        <div className="kpi-value">{stats.earned_credits || 0} TC</div>
                        <div className="kpi-sub">Tổng tích lũy hợp lệ ({progressPercent}% CTĐT)</div>
                      </div>
                      <div className="kpi-card">
                        <div className="kpi-label">Tín chỉ nợ đọng</div>
                        <div className="kpi-value" style={{color: stats.debt_credits > 0 ? 'var(--risk-high)' : 'var(--risk-low)'}}>
                          {stats.debt_credits || 0} TC
                        </div>
                        <div className="kpi-sub">{stats.failed_courses_count || 0} môn chưa đạt</div>
                      </div>
                      <div className="kpi-card">
                        <div className="kpi-label">Điểm trung bình (GPA)</div>
                        <div className="kpi-value">{stats.gpa ? stats.gpa.toFixed(2) : 'N/A'}</div>
                        <div className="kpi-sub">Thang điểm 10.0</div>
                      </div>
                      <div className="kpi-card">
                        <div className="kpi-label">Năm học quy đổi</div>
                        <div className="kpi-value">Năm {stats.academic_year || 1}</div>
                        <div className="kpi-sub">Theo QĐ 753/QĐ-ĐHNT</div>
                      </div>
                    </div>

                    <div className="panel">
                      <div className="panel-header">
                        <h3><User size={18} /> Thông tin chi tiết hồ sơ ({profileSummary.student_id})</h3>
                        <span className="badge badge-low">Bối cảnh: {profileSummary.persona}</span>
                      </div>
                      <div style={{lineHeight: '1.8', fontSize: '0.92rem', color: 'var(--text-secondary)'}}>
                        <p><strong>Mục đích kịch bản:</strong> {profileSummary.persona_purpose || 'N/A'}</p>
                        <p><strong>Phạm vi áp dụng ML:</strong> <code style={{background: 'var(--bg-subtle)', padding: '2px 6px', borderRadius: '4px'}}>{profileSummary.ml_scope}</code> ({profileSummary.ml_scope_reason})</p>
                        <p><strong>Giới hạn đăng ký tín chỉ:</strong> Tối đa {creditRegime.max_credits || 24} TC (Chế độ học vụ: <em>{creditRegime.regime}</em>)</p>
                      </div>
                    </div>
                  </div>
                )}

                {/* TAB 1: Nguy cơ & Giải thích XAI */}
                {currentTab === 1 && (
                  <div>
                    {profileSummary.ml_scope === 'T1_valid' ? (
                      <div>
                        <div className="kpi-grid">
                          <div className="kpi-card">
                            <div className="kpi-label">Xác suất bỏ học (Dropout)</div>
                            <div className="kpi-value" style={{color: riskData.warning_tier === 'high' ? 'var(--risk-high)' : 'var(--risk-low)'}}>
                              {((riskData.p_dropout_calibrated || 0) * 100).toFixed(1)}%
                            </div>
                            <div className="kpi-sub">Đã hiệu chuẩn (Calibrated T1)</div>
                          </div>
                          <div className="kpi-card">
                            <div className="kpi-label">Tầng cảnh báo rủi ro</div>
                            <div className="kpi-value">
                              <span className={`badge badge-${riskData.warning_tier || 'low'}`} style={{fontSize: '0.95rem', padding: '6px 14px'}}>
                                {riskData.warning_tier === 'high' ? 'CAO' : riskData.warning_tier === 'medium' ? 'TRUNG BÌNH' : 'THẤP'}
                              </span>
                            </div>
                            <div className="kpi-sub">Ngưỡng quyết định: {(riskData.threshold_used || 0).toFixed(4)}</div>
                          </div>
                        </div>

                        <div className="panel">
                          <div className="panel-header">
                            <h3><TrendingUp size={18} /> Đóng góp đặc trưng cá nhân hóa (Local SHAP - XAI)</h3>
                            <span className="badge badge-optimal">Top 6 yếu tố tác động</span>
                          </div>
                          <p style={{fontSize: '0.88rem', color: 'var(--text-muted)', marginBottom: '20px'}}>
                            {xaiData.summary}
                          </p>

                          <div>
                            {xaiData.features?.map((feat, idx) => {
                              const isInc = feat.shap_value > 0;
                              const percent = Math.min(100, Math.round(feat.abs_shap * 350));
                              return (
                                <div key={idx} className="shap-bar-container">
                                  <div className="shap-bar-label">
                                    <span>{feat.label_vi}</span>
                                    <span style={{color: isInc ? 'var(--risk-high)' : 'var(--risk-low)'}}>
                                      {isInc ? '+' : ''}{feat.shap_value} ({feat.effect_vi})
                                    </span>
                                  </div>
                                  <div className="shap-bar-track">
                                    <div 
                                      className={`shap-bar-fill ${isInc ? 'shap-bar-inc' : 'shap-bar-dec'}`}
                                      style={{width: `${percent}%`}}
                                    ></div>
                                  </div>
                                </div>
                              );
                            })}
                          </div>

                          <div className="alert-box alert-warning" style={{marginTop: '24px'}}>
                            <Info size={20} />
                            <div>{xaiData.limitation_note}</div>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="alert-box alert-warning">
                        <AlertTriangle size={24} />
                        <div>
                          <strong>Không áp dụng mô hình cảnh báo T1:</strong>
                          <p style={{marginTop: '4px'}}>{xaiData.message}</p>
                          <p style={{marginTop: '4px'}}>
                            Vui lòng tham khảo đánh giá rủi ro dựa trên tiến độ và bộ giải ILP tại <strong>Tab 4. Phương án Đăng ký</strong>.
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* TAB 2: Học phần & Sơ đồ DAG */}
                {currentTab === 2 && (
                  <div>
                    {dagData?.bottlenecks?.length > 0 && (
                      <div className="alert-box alert-danger">
                        <ShieldAlert size={24} />
                        <div>
                          <strong>CẢNH BÁO MÔN HỌC NÚT THẮT (BOTTLENECK):</strong>
                          <p style={{marginTop: '4px'}}>
                            Phát hiện các môn trượt đang khóa chuỗi môn tiên quyết phía sau:
                          </p>
                          <ul style={{marginLeft: '20px', marginTop: '6px'}}>
                            {dagData.bottlenecks.map(b => (
                              <li key={b.course_id}>
                                <strong>{b.course_id} - {b.course_name}</strong>: Đang chặn trực tiếp/gián tiếp <strong>{b.blocked_courses_count} học phần</strong> tiếp theo!
                              </li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    )}

                    <div className="panel">
                      <div className="panel-header">
                        <h3><BookOpen size={18} /> Sơ đồ Phân bố Học phần & Ràng buộc Tiên quyết (DAG)</h3>
                        <span className="badge badge-low">Tổng: {dagData?.total_nodes || 0} môn / {dagData?.total_edges || 0} liên kết</span>
                      </div>

                      <div style={{display: 'flex', gap: '8px', marginBottom: '16px', flexWrap: 'wrap'}}>
                        <span className="badge badge-low">Đã hoàn thành</span>
                        <span className="badge badge-optimal">Đủ điều kiện đăng ký</span>
                        <span className="badge badge-high">Môn nút thắt (Bottleneck)</span>
                        <span className="badge badge-medium">Chưa đủ điều kiện / Bị chặn</span>
                      </div>

                      <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px'}}>
                        {[1, 2, 3, 4, 5, 6, 7, 8].map(sem => {
                          const semNodes = dagData?.nodes?.filter(n => n.planned_semester === sem) || [];
                          return (
                            <div key={sem} style={{background: 'var(--bg-subtle)', padding: '12px', borderRadius: '8px', border: '1px solid var(--border-color)'}}>
                              <div style={{fontWeight: 700, fontSize: '0.85rem', marginBottom: '8px', color: 'var(--edu-primary)'}}>
                                HỌC KỲ {sem}
                              </div>
                              <div style={{display: 'flex', flexDirection: 'column', gap: '6px'}}>
                                {semNodes.length === 0 ? (
                                  <div style={{fontSize: '0.75rem', color: 'var(--text-muted)'}}>Không có môn theo CTĐT chuẩn</div>
                                ) : (
                                  semNodes.map(n => {
                                    let badgeClass = 'badge-medium';
                                    if (n.status === 'completed') badgeClass = 'badge-low';
                                    else if (n.status === 'failed_bottleneck') badgeClass = 'badge-high';
                                    else if (n.status === 'eligible') badgeClass = 'badge-optimal';

                                    return (
                                      <div key={n.id} style={{
                                        background: 'var(--bg-surface)', border: '1px solid var(--border-color)',
                                        padding: '8px 10px', borderRadius: '6px', fontSize: '0.8rem'
                                      }}>
                                        <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                                          <strong style={{color: 'var(--text-primary)'}}>{n.course_id}</strong>
                                          <span className={`badge ${badgeClass}`} style={{fontSize: '0.68rem', padding: '1px 6px'}}>
                                            {n.status === 'completed' ? 'Đã đạt' : n.status === 'failed_bottleneck' ? 'Nút thắt' : n.status === 'eligible' ? 'Đủ ĐK' : 'Bị chặn'}
                                          </span>
                                        </div>
                                        <div style={{color: 'var(--text-secondary)', fontSize: '0.75rem', marginTop: '2px'}}>{n.course_name} ({n.credits}TC)</div>
                                        {n.root_causes?.length > 0 && (
                                          <div style={{color: 'var(--risk-high)', fontSize: '0.72rem', marginTop: '4px', fontWeight: 600}}>
                                            Chặn bởi: {n.root_causes.join(', ')}
                                          </div>
                                        )}
                                      </div>
                                    );
                                  })
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                )}

                {/* TAB 3: Phương án Đăng ký (ILP) */}
                {currentTab === 3 && (
                  <div>
                    <div className="plans-grid">
                      {dssData?.plans?.plans?.map((plan, idx) => {
                        const isFeatured = plan.plan_type === 'balanced';
                        const isHigh = plan.risk_level === 'CAO';
                        return (
                          <div key={idx} className={`plan-card ${isFeatured ? 'plan-featured' : ''}`}>
                            <div className="plan-card-header">
                              <div>
                                <div className="plan-title">{plan.display_label}</div>
                                <div style={{fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px'}}>
                                  Chiến lược: <code>{plan.plan_type}</code>
                                </div>
                              </div>
                              <span className={`badge badge-${isHigh ? 'high' : plan.risk_level === 'TRUNG BÌNH' ? 'medium' : 'low'}`}>
                                Mức: {plan.risk_level}
                              </span>
                            </div>

                            <div style={{marginBottom: '10px'}}>
                              <span className="badge badge-optimal">Trạng thái Solver: {plan.status}</span>
                            </div>

                            <ul className="plan-stats-list">
                              <li className="plan-stats-item">
                                <span style={{color: 'var(--text-secondary)'}}>Tín chỉ lựa chọn:</span>
                                <strong>{plan.selected_credits} TC</strong>
                              </li>
                              <li className="plan-stats-item">
                                <span style={{color: 'var(--text-secondary)'}}>Tín chỉ kỳ vọng đạt:</span>
                                <strong>{Number(plan.expected_credits_passed || 0).toFixed(2)} TC</strong>
                              </li>
                              <li className="plan-stats-item">
                                <span style={{color: 'var(--text-secondary)'}}>Số môn trượt kỳ vọng:</span>
                                <strong style={{color: Number(plan.expected_failed_courses) > 1 ? 'var(--risk-high)' : 'var(--text-primary)'}}>
                                  {Number(plan.expected_failed_courses || 0).toFixed(2)} môn
                                </strong>
                              </li>
                              <li className="plan-stats-item">
                                <span style={{color: 'var(--text-secondary)'}}>Xác suất W1 / W2:</span>
                                <span>P(W1)={Number(plan.p_warning_W1 || 0).toFixed(2)} | P(W2)={Number(plan.p_warning_W2 || 0).toFixed(2)}</span>
                              </li>
                            </ul>

                            <div className="plan-courses-box">
                              <h4>Danh sách học phần ({plan.selected_courses?.length || 0} môn):</h4>
                              {plan.selected_courses?.map(c => (
                                <span key={c.course_id} className="plan-course-tag">
                                  {c.course_id} ({c.credits}TC)
                                </span>
                              ))}
                            </div>

                            {plan.needs_advisor && (
                              <div className="alert-box alert-danger" style={{marginTop: '16px', padding: '10px'}}>
                                <AlertTriangle size={18} />
                                <div style={{fontSize: '0.8rem'}}>
                                  <strong>Khuyến nghị:</strong> Cần tham vấn trực tiếp với Cố vấn học tập trước khi đăng ký.
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* TAB 4: Phân tích What-if */}
                {currentTab === 4 && (
                  <div>
                    <div className="panel">
                      <div className="panel-header">
                        <h3><Sliders size={18} /> Bảng Điều Khiển Tham Số Tối Ưu (Real-time Sliders)</h3>
                        <button 
                          onClick={runWhatIf}
                          className="btn-primary"
                        >
                          Chạy Tối Ưu What-if
                        </button>
                      </div>

                      <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '24px'}}>
                        <div className="slider-group">
                          <div className="slider-header">
                            <span>Hệ số phạt tải (λ)</span>
                            <strong>{wiLambda}</strong>
                          </div>
                          <input 
                            type="range" min="0.0" max="0.5" step="0.05"
                            className="slider-input"
                            value={wiLambda}
                            onChange={e => setWiLambda(parseFloat(e.target.value))}
                          />
                        </div>

                        <div className="slider-group">
                          <div className="slider-header">
                            <span>Trọng số mở khóa (β)</span>
                            <strong>{wiBeta}</strong>
                          </div>
                          <input 
                            type="range" min="0.0" max="0.5" step="0.025"
                            className="slider-input"
                            value={wiBeta}
                            onChange={e => setWiBeta(parseFloat(e.target.value))}
                          />
                        </div>

                        <div className="slider-group">
                          <div className="slider-header">
                            <span>Phạt rủi ro trượt (γ)</span>
                            <strong>{wiGamma}</strong>
                          </div>
                          <input 
                            type="range" min="0.2" max="2.5" step="0.1"
                            className="slider-input"
                            value={wiGamma}
                            onChange={e => setWiGamma(parseFloat(e.target.value))}
                          />
                        </div>
                      </div>
                    </div>

                    {whatIfResult && (
                      <div className="panel">
                        <div className="panel-header">
                          <h3>So sánh: Mặc định (Baseline) vs Phương án What-if</h3>
                          <span className="badge badge-low">Cập nhật động theo trọng số</span>
                        </div>

                        <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '24px'}}>
                          <div>
                            <h4 style={{marginBottom: '12px', color: 'var(--edu-primary)'}}>Phương án Mặc định (Baseline):</h4>
                            {whatIfResult.whatif?.baseline_plans?.map(p => (
                              <div key={p.plan_type} style={{padding: '12px', background: 'var(--bg-subtle)', borderRadius: '8px', marginBottom: '8px', border: '1px solid var(--border-color)'}}>
                                <strong>{p.display_label}</strong>: {p.selected_credits} TC (Kỳ vọng trượt: {Number(p.expected_failed_courses || 0).toFixed(2)} môn)
                              </div>
                            ))}
                          </div>

                          <div>
                            <h4 style={{marginBottom: '12px', color: 'var(--edu-primary-accent)'}}>Phương án What-if mới:</h4>
                            {whatIfResult.whatif?.comparison_plans?.map(p => (
                              <div key={p.plan_type} style={{padding: '12px', background: 'var(--bg-hover)', borderRadius: '8px', marginBottom: '8px', border: '1px solid var(--border-color)'}}>
                                <strong>{p.display_label}</strong>: {p.selected_credits} TC (Kỳ vọng trượt: {Number(p.expected_failed_courses || 0).toFixed(2)} môn)
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* TAB 5: Mô phỏng Monte Carlo */}
                {currentTab === 5 && (
                  <div>
                    <div className="panel">
                      <div className="panel-header">
                        <h3><Activity size={18} /> Mô phỏng Quỹ đạo Dài hạn Monte Carlo (16 Học kỳ)</h3>
                        <div style={{display: 'flex', gap: '8px', alignItems: 'center'}}>
                          <span style={{fontSize: '0.86rem', fontWeight: 600, color: 'var(--text-secondary)'}}>Hệ số phạt λ:</span>
                          {[0.0, 0.1, 0.3].map(l => (
                            <button
                              key={l}
                              onClick={() => setSimLambda(l)}
                              style={{
                                padding: '4px 12px', borderRadius: '6px',
                                background: simLambda === l ? 'var(--edu-primary)' : 'var(--bg-subtle)',
                                color: simLambda === l ? '#ffffff' : 'var(--text-primary)',
                                border: '1px solid var(--border-color)', cursor: 'pointer', fontWeight: 600,
                                fontSize: '0.82rem'
                              }}
                            >
                              λ = {l.toFixed(1)}
                            </button>
                          ))}
                        </div>
                      </div>

                      <div className="data-table-container">
                        <table className="data-table">
                          <thead>
                            <tr>
                              <th>Chính sách</th>
                              <th>P(Tốt nghiệp ≤8 kỳ)</th>
                              <th>P(Tốt nghiệp ≤16 kỳ)</th>
                              <th>Kỳ TN Trung bình</th>
                              <th>Môn trượt kỳ vọng</th>
                              <th>P(Buộc thôi học W1/W2)</th>
                            </tr>
                          </thead>
                          <tbody>
                            {simData?.results?.map((row, idx) => (
                              <tr key={idx}>
                                <td><strong>{row.policy}</strong></td>
                                <td>{Number(row.p_graduated_on_time || 0).toFixed(3)}</td>
                                <td>{Number(row.p_graduated_16 || 0).toFixed(3)}</td>
                                <td>{Number(row.mean_graduation_semester || 0).toFixed(2)}</td>
                                <td>{Number(row.expected_failed_courses || 0).toFixed(2)}</td>
                                <td style={{color: Number(row.p_expelled_regulatory) > 0.1 ? 'var(--risk-high)' : 'inherit'}}>
                                  {Number(row.p_expelled_regulatory || 0).toFixed(3)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>

                      <div className="alert-box alert-warning" style={{marginTop: '20px'}}>
                        <Info size={20} />
                        <div>{simData?.limitation_note}</div>
                      </div>
                    </div>
                  </div>
                )}

                {/* TAB 6: Dữ liệu & Giả định (Provenance) */}
                {currentTab === 6 && (
                  <div>
                    <div className="panel">
                      <div className="panel-header">
                        <h3><Database size={18} /> Hệ Thống Phân Loại Nguồn Dữ Liệu & Giả Định (Academic Provenance)</h3>
                      </div>

                      <div className="prov-item">
                        <strong style={{color: 'var(--edu-primary-accent)'}}>1. REAL (UCI-697):</strong>
                        <p style={{marginTop: '4px', fontSize: '0.88rem', color: 'var(--text-secondary)'}}>
                          Dữ liệu tuyển sinh và kết quả học kỳ 1 của sinh viên đại học (Bồ Đào Nha). Dùng để huấn luyện và đánh giá mô hình ML cảnh báo sớm tại mốc T1. Chưa kiểm định trên sinh viên ĐH Nha Trang.
                        </p>
                      </div>

                      <div className="prov-item">
                        <strong style={{color: 'var(--risk-low)'}}>2. OFFICIAL (NTU):</strong>
                        <p style={{marginTop: '4px', fontSize: '0.88rem', color: 'var(--text-secondary)'}}>
                          Chương trình đào tạo ngành CNTT và Quy chế đào tạo tín chỉ (QĐ 753/QĐ-ĐHNT). Dùng để trích xuất danh mục học phần, quan hệ tiên quyết và kiểm tra điều kiện học vụ.
                        </p>
                      </div>

                      <div className="prov-item">
                        <strong style={{color: 'var(--risk-medium)'}}>3. SCENARIO:</strong>
                        <p style={{marginTop: '4px', fontSize: '0.88rem', color: 'var(--text-secondary)'}}>
                          9 hồ sơ sinh viên kịch bản tổng hợp đại diện cho các tình huống học vụ khác nhau (V2-001 đến V2-009). Không phải thông tin cá nhân của người học thực tế.
                        </p>
                      </div>

                      <div className="prov-item">
                        <strong style={{color: 'var(--risk-high)'}}>4. GIẢ ĐỊNH / UNCONFIRMED:</strong>
                        <p style={{marginTop: '4px', fontSize: '0.88rem', color: 'var(--text-secondary)'}}>
                          Các hệ số phạt (λ, β, γ), xác suất trượt từng môn trong mô phỏng Monte Carlo, và các quy tắc mùa vụ mở môn (chẵn/lẻ) suy diễn từ CTĐT.
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
