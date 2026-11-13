import React, { useState, useEffect } from 'react';
import { 
  User, AlertTriangle, BookOpen, Calendar, Sliders, Activity, 
  Database, CheckCircle, XCircle, Info, ChevronRight, ArrowRight,
  TrendingUp, ShieldAlert, Award, FileText
} from 'lucide-react';

export default function App() {
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

  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1>HỆ HỖ TRỢ QUYẾT ĐỊNH</h1>
          <p>Cảnh báo Rủi ro & Tối ưu Tín chỉ (NTU)</p>
        </div>

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

          {/* Mini Student Info Card */}
          <div className="profile-card">
            <div className="profile-card-row">
              <span className="label">Chuyên ngành:</span>
              <span className="value">{profileSummary.specialization || 'N/A'}</span>
            </div>
            <div className="profile-card-row">
              <span className="label">HK dự kiến:</span>
              <span className="value">Học kỳ {profileSummary.target_semester || 'N/A'}</span>
            </div>
            <div className="profile-card-row">
              <span className="label">Tín chỉ nợ:</span>
              <span className="value" style={{color: stats.debt_credits > 0 ? '#ef4444' : '#10b981'}}>
                {stats.debt_credits || 0} TC
              </span>
            </div>
            <div className="profile-card-row">
              <span className="label">Chế độ QĐ 753:</span>
              <span className="value">{creditRegime.regime || 'normal'}</span>
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
          <div>Trường Đại học Nha Trang - CNTT</div>
          <div style={{marginTop: '2px', opacity: 0.8}}>Khoa Công nghệ Thông tin © 2026</div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="main-wrapper">
        <header className="top-navbar">
          <div className="top-navbar-title">
            <h2>{navItems[currentTab].label}</h2>
            <span className="badge badge-optimal">Hồ sơ: {selectedStudent}</span>
          </div>
          <div style={{fontSize: '0.82rem', color: '#64748b'}}>
            Nhãn nguồn: <span style={{fontWeight: 600, color: '#1B365D'}}>OFFICIAL (NTU) & SCENARIO</span>
          </div>
        </header>

        <main className="main-content">
          {loading ? (
            <div style={{textAlign: 'center', padding: '60px', color: '#64748b'}}>
              Đang tính toán mô hình và nạp dữ liệu sinh viên...
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
                      <div className="kpi-sub">Tổng tích lũy hợp lệ</div>
                    </div>
                    <div className="kpi-card">
                      <div className="kpi-label">Tín chỉ nợ đọng</div>
                      <div className="kpi-value" style={{color: stats.debt_credits > 0 ? '#ef4444' : '#10b981'}}>
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
                      <div className="kpi-sub">Quy chế đào tạo tín chỉ</div>
                    </div>
                  </div>

                  <div className="panel">
                    <div className="panel-header">
                      <h3>Thông tin chi tiết hồ sơ ({profileSummary.student_id})</h3>
                      <span className="badge badge-low">Bối cảnh: {profileSummary.persona}</span>
                    </div>
                    <div style={{lineHeight: '1.7', fontSize: '0.92rem', color: '#334155'}}>
                      <p><strong>Mục đích kịch bản:</strong> {profileSummary.persona_purpose || 'N/A'}</p>
                      <p><strong>Phạm vi ML:</strong> <code>{profileSummary.ml_scope}</code> ({profileSummary.ml_scope_reason})</p>
                      <p><strong>Giới hạn đăng ký tối đa:</strong> {creditRegime.max_credits || 24} tín chỉ (Chế độ: <em>{creditRegime.regime}</em>)</p>
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
                          <div className="kpi-value" style={{color: riskData.warning_tier === 'high' ? '#ef4444' : '#10b981'}}>
                            {((riskData.p_dropout_calibrated || 0) * 100).toFixed(1)}%
                          </div>
                          <div className="kpi-sub">Đã hiệu chuẩn (Calibrated)</div>
                        </div>
                        <div className="kpi-card">
                          <div className="kpi-label">Tầng cảnh báo rủi ro</div>
                          <div className="kpi-value">
                            <span className={`badge badge-${riskData.warning_tier || 'low'}`} style={{fontSize: '1rem', padding: '6px 14px'}}>
                              {riskData.warning_tier === 'high' ? 'CAO' : riskData.warning_tier === 'medium' ? 'TRUNG BÌNH' : 'THẤP'}
                            </span>
                          </div>
                          <div className="kpi-sub">Ngưỡng: {(riskData.threshold_used || 0).toFixed(4)}</div>
                        </div>
                      </div>

                      <div className="panel">
                        <div className="panel-header">
                          <h3>Đóng góp đặc trưng cục bộ (Local SHAP - XAI)</h3>
                          <span className="badge badge-optimal">Top 6 yếu tố cá nhân hóa</span>
                        </div>
                        <p style={{fontSize: '0.88rem', color: '#64748b', marginBottom: '20px'}}>
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
                                  <span style={{color: isInc ? '#ef4444' : '#10b981'}}>
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
                      <h3>Sơ đồ Phân bố Học phần & Ràng buộc Tiên quyết (DAG)</h3>
                      <span className="badge badge-low">Tổng: {dagData?.total_nodes || 0} môn / {dagData?.total_edges || 0} liên kết</span>
                    </div>

                    <div style={{display: 'flex', gap: '8px', marginBottom: '16px', flexWrap: 'wrap'}}>
                      <span className="badge badge-low">Đã hoàn thành</span>
                      <span className="badge badge-optimal">Đủ điều kiện đăng ký</span>
                      <span className="badge badge-high">Môn nút thắt (Bottleneck)</span>
                      <span className="badge badge-medium">Chưa đủ điều kiện / Chặn</span>
                    </div>

                    <div style={{display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px'}}>
                      {[1, 2, 3, 4, 5, 6, 7, 8].map(sem => {
                        const semNodes = dagData?.nodes?.filter(n => n.planned_semester === sem) || [];
                        return (
                          <div key={sem} style={{background: '#f8fafc', padding: '12px', borderRadius: '8px', border: '1px solid #e2e8f0'}}>
                            <div style={{fontWeight: 700, fontSize: '0.85rem', marginBottom: '8px', color: '#1B365D'}}>
                              HỌC KỲ {sem}
                            </div>
                            <div style={{display: 'flex', flexDirection: 'column', gap: '6px'}}>
                              {semNodes.map(n => {
                                let bg = '#ffffff';
                                let border = '#cbd5e1';
                                if (n.status === 'completed') { bg = '#ecfdf5'; border = '#10b981'; }
                                else if (n.status === 'failed_bottleneck') { bg = '#fef2f2'; border = '#ef4444'; }
                                else if (n.status === 'eligible') { bg = '#e0e7ff'; border = '#6366f1'; }

                                return (
                                  <div key={n.id} style={{
                                    background: bg, border: `1px solid ${border}`,
                                    padding: '6px 8px', borderRadius: '6px', fontSize: '0.78rem'
                                  }}>
                                    <div style={{fontWeight: 600}}>{n.course_id}</div>
                                    <div style={{color: '#475569', fontSize: '0.74rem'}}>{n.course_name} ({n.credits}TC)</div>
                                    {n.root_causes?.length > 0 && (
                                      <div style={{color: '#ef4444', fontSize: '0.7rem', marginTop: '2px'}}>
                                        Bị chặn bởi: {n.root_causes.join(', ')}
                                      </div>
                                    )}
                                  </div>
                                );
                              })}
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
                              <div style={{fontSize: '0.8rem', color: '#64748b', marginTop: '2px'}}>
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
                              <span>Tín chỉ lựa chọn:</span>
                              <strong>{plan.selected_credits} TC</strong>
                            </li>
                            <li className="plan-stats-item">
                              <span>Tín chỉ kỳ vọng đạt:</span>
                              <strong>{Number(plan.expected_credits_passed || 0).toFixed(2)} TC</strong>
                            </li>
                            <li className="plan-stats-item">
                              <span>Số môn trượt kỳ vọng:</span>
                              <strong style={{color: Number(plan.expected_failed_courses) > 1 ? '#ef4444' : 'inherit'}}>
                                {Number(plan.expected_failed_courses || 0).toFixed(2)} môn
                              </strong>
                            </li>
                            <li className="plan-stats-item">
                              <span>Xác suất W1 / W2:</span>
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
                      <h3>Bảng Điều Khiển Tham Số Tối Ưu (Real-time Sliders)</h3>
                      <button 
                        onClick={runWhatIf}
                        style={{
                          background: '#1B365D', color: '#ffffff', border: 'none',
                          padding: '8px 18px', borderRadius: '6px', fontWeight: 600, cursor: 'pointer'
                        }}
                      >
                        Chạy Tối Ưu What-if
                      </button>
                    </div>

                    <div style={{display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '24px'}}>
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

                      <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px'}}>
                        <div>
                          <h4 style={{marginBottom: '12px', color: '#1B365D'}}>Phương án Mặc định (Baseline):</h4>
                          {whatIfResult.whatif?.baseline_plans?.map(p => (
                            <div key={p.plan_type} style={{padding: '10px', background: '#f8fafc', borderRadius: '6px', marginBottom: '8px', border: '1px solid #e2e8f0'}}>
                              <strong>{p.display_label}</strong>: {p.selected_credits} TC (Kỳ vọng trượt: {Number(p.expected_failed_courses || 0).toFixed(2)} môn)
                            </div>
                          ))}
                        </div>

                        <div>
                          <h4 style={{marginBottom: '12px', color: '#0284c7'}}>Phương án What-if mới:</h4>
                          {whatIfResult.whatif?.comparison_plans?.map(p => (
                            <div key={p.plan_type} style={{padding: '10px', background: '#f0f9ff', borderRadius: '6px', marginBottom: '8px', border: '1px solid #bae6fd'}}>
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
                      <h3>Mô phỏng Quỹ đạo Dài hạn Monte Carlo (16 Học kỳ)</h3>
                      <div style={{display: 'flex', gap: '8px', alignItems: 'center'}}>
                        <span style={{fontSize: '0.88rem', fontWeight: 600}}>Chọn hệ số phạt λ:</span>
                        {[0.0, 0.1, 0.3].map(l => (
                          <button
                            key={l}
                            onClick={() => setSimLambda(l)}
                            style={{
                              padding: '4px 12px', borderRadius: '6px',
                              background: simLambda === l ? '#1B365D' : '#f1f5f9',
                              color: simLambda === l ? '#ffffff' : '#334155',
                              border: '1px solid #cbd5e1', cursor: 'pointer', fontWeight: 600
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
                              <td style={{color: Number(row.p_expelled_regulatory) > 0.1 ? '#ef4444' : 'inherit'}}>
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
                      <h3>Hệ Thống Phân Loại Nguồn Dữ Liệu & Giả Định (Academic Provenance)</h3>
                    </div>

                    <div className="prov-item">
                      <strong style={{color: '#0284c7'}}>1. REAL (UCI-697):</strong>
                      <p style={{marginTop: '4px', fontSize: '0.88rem'}}>
                        Dữ liệu tuyển sinh và kết quả học kỳ 1 của sinh viên đại học (Bồ Đào Nha). Dùng để huấn luyện và đánh giá mô hình ML cảnh báo sớm tại mốc T1. Chưa kiểm định trên sinh viên ĐH Nha Trang.
                      </p>
                    </div>

                    <div className="prov-item">
                      <strong style={{color: '#10b981'}}>2. OFFICIAL (NTU):</strong>
                      <p style={{marginTop: '4px', fontSize: '0.88rem'}}>
                        Chương trình đào tạo ngành CNTT và Quy chế đào tạo tín chỉ (QĐ 753/QĐ-ĐHNT). Dùng để trích xuất danh mục học phần, quan hệ tiên quyết và kiểm tra điều kiện học vụ.
                      </p>
                    </div>

                    <div className="prov-item">
                      <strong style={{color: '#f59e0b'}}>3. SCENARIO:</strong>
                      <p style={{marginTop: '4px', fontSize: '0.88rem'}}>
                        9 hồ sơ sinh viên kịch bản tổng hợp đại diện cho các tình huống học vụ khác nhau (V2-001 đến V2-009). Không phải thông tin cá nhân của người học thực tế.
                      </p>
                    </div>

                    <div className="prov-item">
                      <strong style={{color: '#ef4444'}}>4. GIẢ ĐỊNH / UNCONFIRMED:</strong>
                      <p style={{marginTop: '4px', fontSize: '0.88rem'}}>
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
  );
}
