import React from 'react';
import { formatRepairLocation } from '../../lib/repairLocation';
import { X, Star } from 'lucide-react';
import { RepairRequest } from '../../types';
import { API } from '../../lib/api';
import { useLanguage } from '../../contexts/LanguageContext';
import { Badge, SlaBadge } from './StatusBadge';
import ConsumedPartsList from './ConsumedPartsList';
import { tCat, tStatus, tPriority, STATUS_COLOR, PRIORITY_COLOR } from './constants';

export default function RepairDetailModal({ repair, token, onClose }: {
  repair: RepairRequest | null;
  token: string | null;
  onClose: () => void;
}) {
  const { language, t } = useLanguage();
  if (!repair) return null;
  const date = (value?: string) => value ? new Date(value).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-US') : '—';
  const imageUrl = (url: string) => url.startsWith('http') || url.startsWith('data:') ? url : `${API.BASE}${url}`;

  return (
    <div className="fixed inset-0 z-[100] flex items-end justify-center bg-black/50 sm:items-center sm:p-4"
      onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section role="dialog" aria-modal="true" aria-label={language === 'zh' ? '报修详情' : 'Repair details'}
        className="flex max-h-[92dvh] w-full max-w-2xl flex-col overflow-hidden rounded-t-2xl bg-white shadow-2xl sm:max-h-[88vh] sm:rounded-2xl">
        <header className="flex shrink-0 items-center justify-between border-b border-border px-4 py-3 sm:px-6">
          <div>
            <h2 className="font-bold text-foreground">{language === 'zh' ? '报修详情' : 'Repair details'}</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">#{repair.id}</p>
          </div>
          <button type="button" onClick={onClose} aria-label={language === 'zh' ? '关闭' : 'Close'}
            className="rounded-full p-2 text-muted-foreground hover:bg-muted"><X className="h-5 w-5" /></button>
        </header>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain px-4 py-4 touch-pan-y sm:px-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <h3 className="break-words text-lg font-semibold text-foreground">{formatRepairLocation(repair.dormBuilding, repair.dormFloor, repair.dormRoom)}</h3>
              <div className="mt-2 flex flex-wrap gap-2">
                <Badge label={tCat(repair.category, t)} colorClass="bg-gray-100 text-gray-700" />
                <Badge label={tPriority(repair.priority, t)} colorClass={PRIORITY_COLOR[repair.priority]} />
                <Badge label={tStatus(repair.status, t)} colorClass={STATUS_COLOR[repair.status]} />
              </div>
            </div>
            <SlaBadge slaDueDate={repair.slaDueDate} status={repair.status} />
          </div>

          <section className="rounded-xl bg-muted/40 p-3 text-sm">
            <h4 className="mb-2 font-semibold text-foreground">{language === 'zh' ? '报修信息' : 'Request information'}</h4>
            <dl className="grid grid-cols-1 gap-x-4 gap-y-2 sm:grid-cols-2">
              <div><dt className="text-xs text-muted-foreground">{language === 'zh' ? '报修人' : 'Reported by'}</dt><dd className="break-words">{repair.userName || '—'}</dd></div>
              <div><dt className="text-xs text-muted-foreground">{language === 'zh' ? '联系电话' : 'Phone'}</dt><dd>{repair.userPhone || '—'}</dd></div>
              <div><dt className="text-xs text-muted-foreground">{language === 'zh' ? '维修员' : 'Repairman'}</dt><dd>{repair.assignedToName || '—'}</dd></div>
              <div><dt className="text-xs text-muted-foreground">{language === 'zh' ? '优先级' : 'Priority'}</dt><dd>{tPriority(repair.priority, t)}</dd></div>
              <div><dt className="text-xs text-muted-foreground">{language === 'zh' ? '提交时间' : 'Created'}</dt><dd>{date(repair.createdAt)}</dd></div>
              <div><dt className="text-xs text-muted-foreground">{language === 'zh' ? '更新时间' : 'Updated'}</dt><dd>{date(repair.updatedAt)}</dd></div>
              {repair.slaDueDate && <div><dt className="text-xs text-muted-foreground">SLA</dt><dd>{date(repair.slaDueDate)}</dd></div>}
            </dl>
          </section>

          <section>
            <h4 className="mb-2 text-sm font-semibold text-foreground">{t('faultDescription')}</h4>
            <div className="min-h-44 max-h-80 overflow-y-auto overscroll-contain rounded-xl border border-border bg-muted/20 p-3 text-sm leading-relaxed text-foreground whitespace-pre-wrap break-words touch-pan-y">{repair.description}</div>
          </section>

          {repair.imageUrl && <section>
            <h4 className="mb-2 text-sm font-semibold text-foreground">{language === 'zh' ? '报修图片' : 'Photos'}</h4>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {repair.imageUrl.split(',').filter(Boolean).map((url, index) => <a key={index} href={imageUrl(url)} target="_blank" rel="noreferrer"
                className="block aspect-video overflow-hidden rounded-xl border border-border bg-muted">
                <img src={imageUrl(url)} alt={`Repair ${index + 1}`} className="h-full w-full object-cover" />
              </a>)}
            </div>
          </section>}

          {repair.adminNote && <section><h4 className="mb-1 text-sm font-semibold">{language === 'zh' ? '管理员备注' : 'Admin note'}</h4><p className="whitespace-pre-wrap break-words rounded-xl bg-muted/40 p-3 text-sm">{repair.adminNote}</p></section>}
          {repair.workNote && <section><h4 className="mb-1 text-sm font-semibold">{language === 'zh' ? '维修记录' : 'Repair notes'}</h4><p className="whitespace-pre-wrap break-words rounded-xl bg-muted/40 p-3 text-sm">{repair.workNote}</p></section>}
          {!!repair.rating && repair.rating > 0 && <section className="rounded-xl bg-yellow-50 p-3">
            <h4 className="mb-2 text-sm font-semibold">{language === 'zh' ? '学生评价' : 'Rating'}</h4>
            <div className="flex gap-1">{[1,2,3,4,5].map((n) => <Star key={n} className={`h-5 w-5 ${n <= repair.rating! ? 'fill-current text-yellow-400' : 'text-gray-200'}`} />)}</div>
          </section>}
          <ConsumedPartsList repairId={repair.id} token={token} status={repair.status} />
        </div>
        <footer className="shrink-0 border-t border-border p-3 sm:px-6">
          <button type="button" onClick={onClose} className="w-full rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-white">{language === 'zh' ? '关闭' : 'Close'}</button>
        </footer>
      </section>
    </div>
  );
}

