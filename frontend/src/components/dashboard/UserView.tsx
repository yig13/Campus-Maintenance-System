import React, { useState, useEffect, useCallback } from 'react';
import { useLanguage } from '../../contexts/LanguageContext';
import { authFetch, API, readApiMessage } from '../../lib/api';
import { toast } from 'sonner';
import { RepairRequest, ApiResponse, PaginatedApiResponse } from '../../types';
import {
  Plus, Star, ChevronRight, RefreshCw, Send, ClipboardList
} from 'lucide-react';
import EvaluationModal from '../custom/EvaluationModal';
import Pagination from '../custom/Pagination';
import { Badge, SlaBadge } from '../shared/StatusBadge';
import ConsumedPartsList from '../shared/ConsumedPartsList';
import RepairDetailModal from '../shared/RepairDetailModal';
import { compressImageForUpload } from '../../lib/imageCompression';
import { formatRepairLocation } from '../../lib/repairLocation';
import {
  tCat, tStatus, tPriority, STATUS_COLOR, PRIORITY_COLOR,
  DORM_BUILDING_GROUPS, FAULT_CATEGORY_GROUPS,
} from '../shared/constants';

export default function UserView({ token }: { token: string | null }) {
  const { language, t } = useLanguage();
  const [view, setView] = useState<'list' | 'new' | 'detail'>('list');
  const [requests, setRequests] = useState<RepairRequest[]>([]);
  const [selected, setSelected] = useState<RepairRequest | null>(null);
  const [detailTarget, setDetailTarget] = useState<RepairRequest | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [evalModalOpen, setEvalModalOpen] = useState(false);
  const [evalLoading, setEvalLoading] = useState(false);
  const [evalTarget, setEvalTarget] = useState<RepairRequest | null>(null);
  const [form, setForm] = useState({
    dormBuilding: '', dormFloor: '', dormRoom: '', category: '',
    description: '', imageUrl: '',
  });
  const roomRequired = form.dormBuilding.startsWith('公寓');
  const floorRequired = roomRequired;

  const [currentPage, setCurrentPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const pageSize = 5;

  const loadRequests = useCallback(async () => {
    setLoading(true);
    try {
      const url = `${API.REPAIRS.LIST}?page=${currentPage}&pageSize=${pageSize}`;
      const res = await authFetch(url, token);
      const data = await res.json() as PaginatedApiResponse<RepairRequest[]>;
      if (data.success) {
        setRequests(data.data);
        setTotalCount(data.total ?? data.data.length);
      }
    } catch { toast.error(language === 'zh' ? '加载失败' : 'Load failed'); }
    finally { setLoading(false); }
  }, [token, currentPage, pageSize, language]);

  useEffect(() => { loadRequests(); }, [loadRequests]);

  async function submitRepair(e: React.FormEvent) {
    e.preventDefault();
    if (!form.dormBuilding || (floorRequired && !form.dormFloor) || (roomRequired && !form.dormRoom.trim()) || !form.category || !form.description) {
      toast.error(language === 'zh' ? '请填写所有必填项' : 'Please fill in all required fields'); return;
    }
    setSubmitting(true);
    try {
      const res = await authFetch(API.REPAIRS.CREATE, token, {
        method: 'POST',
        body: JSON.stringify({
          dormBuilding: form.dormBuilding,
          dormFloor: form.dormFloor ? Number(form.dormFloor) : undefined,
          dormRoom: form.dormRoom,
          category: form.category,
          description: form.description,
          imageUrl: form.imageUrl || undefined,
        }),
      });
      const data = await res.json() as ApiResponse<RepairRequest>;
      if (data.success) {
        toast.success(language === 'zh' ? '报修申请提交成功！' : 'Repair request submitted successfully!');
        setForm({ dormBuilding: '', dormFloor: '', dormRoom: '', category: '', description: '', imageUrl: '' });
        setCurrentPage(1);
        setView('list');
        loadRequests();
      } else {
        toast.error(data.message || await readApiMessage(res, language === 'zh' ? `提交失败 (HTTP ${res.status})` : `Submission failed (HTTP ${res.status})`));
      }
    } catch (err) {
      console.error('Submit repair error:', err);
      toast.error(language === 'zh' ? '网络错误，请稍后重试' : 'Network error, please try again later');
    }
    finally { setSubmitting(false); }
  }

  /** 提交评价（通过新接口） */
  async function handleEvaluate(rating: number) {
    if (!evalTarget) return;
    setEvalLoading(true);
    try {
      const res = await authFetch(API.REPAIRS.EVALUATE(evalTarget.id), token, {
        method: 'POST',
        body: JSON.stringify({
          rating,
        }),
      });
      const data = await res.json() as ApiResponse<RepairRequest>;
      if (data.success) {
        toast.success(language === 'zh' ? '评价提交成功！感谢您的反馈' : 'Evaluation submitted! Thank you for your feedback');
        setEvalModalOpen(false);
        setEvalTarget(null);
        loadRequests();
      } else {
        toast.error(data.message || await readApiMessage(res, language === 'zh' ? '评价提交失败' : 'Failed to submit evaluation'));
      }
    } catch { toast.error(language === 'zh' ? '网络错误' : 'Network error'); }
    finally { setEvalLoading(false); }
  }

  if (view === 'new') {
    return (
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <button onClick={() => setView('list')} className="text-muted-foreground hover:text-foreground">
            <ChevronRight className="w-5 h-5 rotate-180" />
          </button>
          <h2 className="text-xl font-bold text-foreground">{t('requestRepair')}</h2>
        </div>
        <div className="bg-white rounded-2xl shadow-sm border border-border p-6">
          <form onSubmit={submitRepair} className="space-y-5">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="sm:col-start-1 sm:row-start-1">
                <label className="block text-sm font-medium text-foreground mb-1">{t('dormBuilding')} <span className="text-red-500">*</span></label>
                <select
                  required
                  value={form.dormBuilding}
                  onChange={(e) => setForm((p) => ({ ...p, dormBuilding: e.target.value, dormFloor: e.target.value.startsWith('公寓') ? p.dormFloor : '' }))}
                  className="w-full px-4 py-2.5 rounded-xl border border-border bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition"
                >
                  <option value="" disabled>{language === 'zh' ? '请选择楼栋' : 'Select building'}</option>
                  {DORM_BUILDING_GROUPS.map((group) => (
                    <optgroup key={group.group} label={group.group}>
                      {group.options.map((building) => (
                        <option key={building} value={building}>{building}</option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </div>
              <div className="order-3 sm:col-start-2 sm:row-start-1">
                <label className="block text-sm font-medium text-foreground mb-1">
                  {t('floor')} {floorRequired && <span className="text-red-500">*</span>}
                </label>
                <select
                  required={floorRequired}
                  value={form.dormFloor}
                  onChange={(e) => setForm((p) => ({ ...p, dormFloor: e.target.value }))}
                  className="w-full px-4 py-2.5 rounded-xl border border-border bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition"
                >
                  <option value="">{language === 'zh' ? '请选择楼层' : 'Select floor'}</option>
                  {Array.from({ length: 10 }, (_, i) => i + 1).map((floor) => (
                    <option key={floor} value={floor}>{language === 'zh' ? `${floor}层` : `Floor ${floor}`}</option>
                  ))}
                </select>
              </div>
              <div className="order-2 sm:col-start-1 sm:row-start-2">
                <label className="block text-sm font-medium text-foreground mb-1">
                  {t('roomNumber')} {roomRequired && <span className="text-red-500">*</span>}
                </label>
                <input value={form.dormRoom} required={roomRequired} onChange={(e) => setForm(p => ({ ...p, dormRoom: e.target.value }))}
                  placeholder={roomRequired ? '如：301' : (language === 'zh' ? '公共区域可不填，或填写具体位置' : 'Optional for public areas; enter a specific location if needed')}
                  className="w-full px-4 py-2.5 rounded-xl border border-border bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition" />
              </div>
              <div className="sm:col-start-2 sm:row-start-2">
                <label className="block text-sm font-medium text-foreground mb-1">{t('faultCategory')} <span className="text-red-500">*</span></label>
                <select
                  required
                  value={form.category}
                  onChange={(e) => setForm(p => ({ ...p, category: e.target.value }))}
                  className="w-full px-4 py-2.5 rounded-xl border border-border bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition"
                >
                  <option value="" disabled>{language === 'zh' ? '请选择故障分类' : 'Select category'}</option>
                  {FAULT_CATEGORY_GROUPS.map((g) => (
                    <optgroup key={g.group} label={g.group}>
                      {g.options.map((opt) => (
                        <option key={opt.value} value={opt.value} disabled={opt.disabled}>
                          {tCat(opt.value, t)}
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1.5">{t('faultDescription')} <span className="text-red-500">*</span></label>
              <textarea value={form.description} onChange={(e) => setForm(p => ({ ...p, description: e.target.value }))}
                rows={4} maxLength={50} placeholder={t('describePlaceholder')}
                className="w-full px-4 py-2.5 rounded-xl border border-border bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition resize-none" />
              <p className="mt-1 text-right text-xs text-muted-foreground">{form.description.length}/50</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">{t('uploadPhoto')} <span className="font-normal text-muted-foreground">({t('photoUploadHint')})</span></label>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-2">
                {/* 渲染已有图片的缩略图 */}
                {form.imageUrl ? form.imageUrl.split(',').map((imgUrl, idx) => (
                  <div key={idx} className="relative aspect-square rounded-xl overflow-hidden border border-border group bg-muted flex items-center justify-center">
                    <img
                      src={imgUrl.startsWith('http') || imgUrl.startsWith('data:') ? imgUrl : `${API.BASE}${imgUrl}`}
                      alt={`预览图片 ${idx + 1}`}
                      className="w-full h-full object-cover"
                    />
                    <button
                      type="button"
                      onClick={() => {
                        const urls = form.imageUrl.split(',');
                        urls.splice(idx, 1);
                        setForm(p => ({ ...p, imageUrl: urls.join(',') }));
                      }}
                      className="absolute top-1.5 right-1.5 p-1 rounded-full bg-red-500 text-white hover:bg-red-600 transition shadow opacity-90 hover:opacity-100"
                    >
                      <Plus className="w-3.5 h-3.5 rotate-45" />
                    </button>
                  </div>
                )) : null}

                {/* 如果上传的图片小于 5 张，显示上传按钮 */}
                {(!form.imageUrl || form.imageUrl.split(',').filter(Boolean).length < 3) && (
                  <label className="border-2 border-dashed border-border hover:border-primary/60 rounded-xl flex flex-col items-center justify-center cursor-pointer transition bg-background hover:bg-muted/10 aspect-square min-h-[96px]">
                    <input
                      type="file"
                      accept="image/*"
                      disabled={submitting}
                      className="hidden"
                      onChange={async (e) => {
                        const input = e.currentTarget;
                        const file = input.files?.[0];
                        if (!file) return;
                        if ((form.imageUrl ? form.imageUrl.split(',').filter(Boolean).length : 0) >= 3) {
                          toast.error(language === 'zh' ? '最多上传3张故障照片' : 'You can upload up to 3 photos');
                          input.value = '';
                          return;
                        }
                        setSubmitting(true);
                        try {
                          const uploadFile = await compressImageForUpload(file);
                          const formData = new FormData();
                          formData.append('file', uploadFile);
                          const res = await authFetch(API.UPLOAD, token, {
                            method: 'POST',
                            body: formData,
                          });
                          const data = await res.json() as { success: boolean; url: string; message?: string };
                          if (data.success) {
                            const currentUrls = form.imageUrl ? form.imageUrl.split(',') : [];
                            currentUrls.push(data.url);
                            setForm(p => ({ ...p, imageUrl: currentUrls.join(',') }));
                            toast.success(language === 'zh' ? '图片上传成功！' : 'Image uploaded successfully!');

                          } else {
                            toast.error(data.message || (language === 'zh' ? '图片上传失败' : 'Image upload failed'));
                          }
                        } catch (error) {
                          const message = error instanceof Error ? error.message : '';
                          toast.error(message || (language === 'zh' ? '上传图片时发生网络错误' : 'Network error during image upload'));
                        } finally {
                          setSubmitting(false);
                          input.value = '';
                        }
                      }}
                    />
                    <Plus className="w-5 h-5 text-muted-foreground mb-1" />
                    <span className="text-xs text-muted-foreground text-center px-1 font-medium">{language === 'zh' ? '添加图片' : 'Add Image'}</span>
                    <span className="text-[10px] text-muted-foreground/60 text-center">{form.imageUrl ? form.imageUrl.split(',').filter(Boolean).length : 0}/3</span>
                  </label>
                )}
              </div>
            </div>

            <div className="flex gap-3 pt-2">
              <button type="button" onClick={() => setView('list')}
                className="flex-1 py-3 rounded-xl border border-border text-foreground font-medium hover:bg-muted transition">
                {t('cancel')}
              </button>
              <button type="submit" disabled={submitting}
                className="flex-1 py-3 bg-primary text-primary-foreground rounded-xl font-semibold hover:opacity-90 transition disabled:opacity-50 flex items-center justify-center gap-2">
                <Send className="w-4 h-4" />{submitting ? t('loading') : t('submit')}
              </button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  if (view === 'detail' && selected) {
    return (
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <button onClick={() => setView('list')} className="text-muted-foreground hover:text-foreground">
            <ChevronRight className="w-5 h-5 rotate-180" />
          </button>
          <h2 className="text-xl font-bold text-foreground">{language === 'zh' ? '报修详情' : 'Repair Details'}</h2>
        </div>
        <div className="bg-white rounded-2xl shadow-sm border border-border p-6 space-y-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-lg font-semibold text-foreground">{formatRepairLocation(selected.dormBuilding, selected.dormFloor, selected.dormRoom)}</p>
              <p className="text-sm text-muted-foreground mt-0.5">{tCat(selected.category, t)}</p>
            </div>
            <div className="flex flex-col items-end gap-1">
              <Badge label={tStatus(selected.status, t)} colorClass={STATUS_COLOR[selected.status]} />
              <Badge label={tPriority(selected.priority, t)} colorClass={PRIORITY_COLOR[selected.priority]} />
              <SlaBadge slaDueDate={selected.slaDueDate} status={selected.status} />
            </div>
          </div>
          <div className="border-t border-border pt-4">
            <p className="text-sm font-medium text-muted-foreground mb-1">{t('faultDescription')}</p>
            <p className="text-foreground leading-relaxed">{selected.description}</p>
          </div>
          {selected.imageUrl && (
            <div className="border-t border-border pt-4">
              <p className="text-sm font-medium text-muted-foreground mb-2">{language === 'zh' ? '报修图片' : 'Repair Photos'}</p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {selected.imageUrl.split(',').map((imgUrl, idx) => (
                  <div key={idx} className="relative aspect-video rounded-xl overflow-hidden border border-border bg-muted flex items-center justify-center cursor-zoom-in">
                    <img
                      src={imgUrl.startsWith('http') || imgUrl.startsWith('data:') ? imgUrl : `${API.BASE}${imgUrl}`}
                      alt={`报修图片 ${idx + 1}`}
                      className="w-full h-full object-cover hover:scale-105 transition-transform duration-200"
                      onClick={() => window.open(imgUrl.startsWith('http') || imgUrl.startsWith('data:') ? imgUrl : `${API.BASE}${imgUrl}`, '_blank')}
                    />
                  </div>
                ))}
              </div>
            </div>
          )}
          {selected.adminNote && (
            <div className="border-t border-border pt-4">
              <p className="text-sm font-medium text-muted-foreground mb-1">{language === 'zh' ? '管理员备注' : 'Admin Note'}</p>
              <p className="text-foreground">{selected.adminNote}</p>
            </div>
          )}
          {selected.assignedToName && (
            <div className="border-t border-border pt-4">
              <p className="text-sm font-medium text-muted-foreground mb-1">{language === 'zh' ? '维修人员' : 'Repairman'}</p>
              <p className="text-foreground">{selected.assignedToName}</p>
            </div>
          )}
          <div className="border-t border-border pt-4 text-sm text-muted-foreground">
            {language === 'zh' ? '提交时间：' : 'Submitted At: '}{new Date(selected.createdAt).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-US')}
          </div>

          {/* 评价信息显示 */}
          {selected.rating && selected.rating > 0 && (
            <div className="border-t border-border pt-4">
              <p className="text-sm font-semibold text-foreground mb-2">{language === 'zh' ? '服务评价' : 'Service Evaluation'}</p>
              <div className="flex items-center gap-1 mb-2">
                {[1,2,3,4,5].map((s) => (
                  <Star key={s} className={`w-5 h-5 ${s <= selected.rating! ? 'text-yellow-400 fill-current' : 'text-gray-200'}`} />
                ))}
              </div>
            </div>
          )}
          <ConsumedPartsList repairId={selected.id} token={token} status={selected.status} />
        </div>

      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-foreground">{t('myRepairs')}</h2>
        <div className="flex gap-2">
          <button onClick={loadRequests} className="p-2 rounded-xl border border-border hover:bg-muted transition hover:scale-105 active:scale-95 duration-200" title={language === 'zh' ? '刷新列表' : 'Refresh List'}>
            <RefreshCw className={`w-4 h-4 text-muted-foreground ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button onClick={() => setView('new')}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-xl font-medium hover:opacity-90 transition">
            <Plus className="w-4 h-4" />{t('requestRepair')}
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <RefreshCw className="w-6 h-6 text-muted-foreground animate-spin" />
        </div>
      ) : requests.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <ClipboardList className="w-12 h-12 text-muted-foreground mb-3" />
          <p className="text-muted-foreground">{t('noData')}</p>
          <button onClick={() => setView('new')}
            className="mt-4 px-6 py-2.5 bg-primary text-primary-foreground rounded-xl font-medium hover:opacity-90 transition">
            {t('requestRepair')}
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {requests.map((r) => (
            <div key={r.id} className="bg-white rounded-2xl shadow-sm border border-border p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0 cursor-pointer"
                  onClick={() => setDetailTarget(r)}>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-foreground">{formatRepairLocation(r.dormBuilding, r.dormFloor, r.dormRoom)}</span>
                    <Badge label={tCat(r.category, t)} colorClass="bg-gray-100 text-gray-700" />
                  </div>
                  <p className="text-sm text-muted-foreground mt-1 line-clamp-2">{r.description}</p>
                  <p className="text-xs text-muted-foreground mt-2">{new Date(r.createdAt).toLocaleDateString(language === 'zh' ? 'zh-CN' : 'en-US')}</p>
                  {/* 已评价工单显示星级 */}
                  {r.rating && r.rating > 0 && (
                    <div className="flex items-center gap-1 mt-1">
                      {[1,2,3,4,5].map((s) => (
                        <Star key={s} className={`w-3 h-3 ${s <= r.rating! ? 'text-yellow-400 fill-current' : 'text-gray-200'}`} />
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex flex-col items-end gap-2 shrink-0">
                  <Badge label={tStatus(r.status, t)} colorClass={STATUS_COLOR[r.status]} />
                  <Badge label={tPriority(r.priority, t)} colorClass={PRIORITY_COLOR[r.priority]} />
                  <SlaBadge slaDueDate={r.slaDueDate} status={r.status} />
                </div>
              </div>
              {/* 待评价按钮放在工单标签下方，保持原有黄色样式。 */}
              {r.status === 'pending_evaluation' && (
                <div className="mt-3 pt-3 border-t border-border">
                  <button
                    onClick={() => { setEvalTarget(r); setEvalModalOpen(true); }}
                    className="w-full py-2 bg-yellow-500 text-white rounded-xl text-sm font-bold hover:bg-yellow-600 transition animate-pulse shadow-lg shadow-yellow-200"
                  >
                    {language === 'zh' ? '去评价' : 'Evaluate'}
                  </button>
                </div>
              )}
            </div>
          ))}
          <Pagination
            currentPage={currentPage}
            totalCount={totalCount}
            pageSize={pageSize}
            onPageChange={setCurrentPage}
          />
        </div>
      )}

      {/* 评价弹窗 */}
      <EvaluationModal
        open={evalModalOpen}
        onClose={() => { setEvalModalOpen(false); setEvalTarget(null); }}
        onSubmit={handleEvaluate}
        loading={evalLoading}
      />
      <RepairDetailModal repair={detailTarget} token={token} onClose={() => setDetailTarget(null)} />
    </div>
  );
}
