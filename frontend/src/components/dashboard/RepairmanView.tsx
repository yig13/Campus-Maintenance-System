import React, { useState, useEffect, useCallback } from 'react';
import { useLanguage } from '../../contexts/LanguageContext';
import { formatRepairLocation } from '../../lib/repairLocation';
import { authFetch, API, readApiMessage } from '../../lib/api';
import { toast } from 'sonner';
import { RepairRequest, Part, ApiResponse } from '../../types';
import {
  Wrench, Star, RefreshCw, Clock, CheckCircle, BarChart2
} from 'lucide-react';
import { Badge, SlaBadge } from '../shared/StatusBadge';
// import ConsumedPartsList from '../shared/ConsumedPartsList'; // 暂时隐藏物料消耗展示。
import RepairDetailModal from '../shared/RepairDetailModal';
import Pagination from '../custom/Pagination';
import { tCat, tStatus, tPriority, STATUS_COLOR, PRIORITY_COLOR } from '../shared/constants';

export default function RepairmanView({ token }: { token: string | null }) {
  const { language, t } = useLanguage();
  const [tasks, setTasks] = useState<RepairRequest[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<RepairRequest | null>(null);
  const [detailTarget, setDetailTarget] = useState<RepairRequest | null>(null);
  const [workNote, setWorkNote] = useState('');
  const [updating, setUpdating] = useState(false);
  const [tab, setTab] = useState<'tasks' | 'stats'>('tasks');
  const [taskStatusFilter, setTaskStatusFilter] = useState<'waiting' | 'ready' | 'in_progress' | 'completed'>('waiting');
  const [tasksPage, setTasksPage] = useState(1);
  const [tasksTotal, setTasksTotal] = useState(0);
  const [statusCounts, setStatusCounts] = useState({ waiting: 0, ready: 0, in_progress: 0, completed: 0, averageRating: 0, ratingCount: 0, totalAssigned: 0 });
  const tasksPageSize = 20;

  // parts state
  const [inventoryParts, setInventoryParts] = useState<Part[]>([]);
  const [selectedParts, setSelectedParts] = useState<{ [partId: string]: number }>({});

  const loadTasks = useCallback(async () => {
    setLoading(true);
    try {
      const query = new URLSearchParams({ page: String(tasksPage), pageSize: String(tasksPageSize), status: taskStatusFilter });
      const res = await authFetch(`${API.REPAIRS.LIST}?${query}`, token);
      const data = await res.json() as ApiResponse<RepairRequest[]> & {
        total?: number;
        statusCounts?: typeof statusCounts;
      };
      if (data.success) {
        setTasks(data.data);
        setTasksTotal(data.total ?? data.data.length);
        if (data.statusCounts) setStatusCounts(data.statusCounts);
      }
      else toast.error(data.message || (language === 'zh' ? '加载失败' : 'Load failed'));
    } catch { toast.error(language === 'zh' ? '加载失败，请确认后端服务已启动' : 'Load failed, make sure backend service is running'); }
    finally { setLoading(false); }
  }, [token, language, tasksPage, tasksPageSize, taskStatusFilter]);

  const loadInventoryParts = useCallback(async () => {
    if (!token) return;
    try {
      const res = await authFetch(API.PARTS.LIST, token);
      const data = await res.json() as ApiResponse<Part[]>;
      if (data.success) setInventoryParts(data.data);
    } catch (err) {
      console.error('Failed to load inventory parts:', err);
    }
  }, [token]);

  useEffect(() => {
    loadTasks();
    // 物料消耗界面暂时隐藏，保留库存加载函数以便后续恢复。
    // loadInventoryParts();
  }, [loadTasks, loadInventoryParts]);

  useEffect(() => {
    if (tab !== 'tasks') return;
    const refreshTimer = window.setInterval(loadTasks, 30000);
    return () => window.clearInterval(refreshTimer);
  }, [loadTasks, tab]);

  async function updateTask(taskId: string, status: string) {
    setUpdating(true);
    try {
      const res = await authFetch(API.REPAIRS.UPDATE_STATUS(taskId), token, {
        method: 'PATCH',
        body: JSON.stringify({
          status,
          // 后端仍要求维修记录字段，前端不再收集时传入默认值。
          workNote: status === 'completed' ? '维修已完成' : (workNote || undefined),
        }),
      });
      const data = await res.json() as ApiResponse<RepairRequest>;
      if (data.success) {
        toast.success(language === 'zh' ? '任务状态已更新' : 'Task status updated');
        setSelected(null);
        setWorkNote('');
        setSelectedParts({});
        loadTasks();
        // 物料消耗界面暂时隐藏，完成工单后无需刷新库存。
        // loadInventoryParts();
      } else {
        toast.error(data.message || await readApiMessage(res, language === 'zh' ? '更新失败' : 'Failed to update'));
      }
    } catch { toast.error(language === 'zh' ? '网络错误' : 'Network error'); }
    finally { setUpdating(false); }
  }


  const filteredTasks = tasks;

  const pending = statusCounts.waiting;
  const ready = statusCounts.ready;
  const inProgress = statusCounts.in_progress;
  const avgRating = statusCounts.ratingCount > 0 ? statusCounts.averageRating.toFixed(1) : '暂无';

  return (
    <div>
      {/* Tabs */}
      <div className="flex gap-1 bg-muted rounded-xl p-1 mb-6">
        {([['tasks', t('tabTasks'), Wrench], ['stats', t('tabMyPerformance'), BarChart2]] as const).map(([key, label, Icon]) => (
          <button key={key} onClick={() => setTab(key as 'tasks' | 'stats')}
            className={`flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg text-sm font-medium transition ${
              tab === key ? 'bg-white text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
            }`}>
            <Icon className="w-4 h-4" />
            <span className="hidden sm:inline">{label}</span>
          </button>
        ))}
      </div>

      {tab === 'tasks' && (
        <>
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-foreground">{t('tabTasks')}</h3>
            <button onClick={loadTasks} className="p-2 rounded-xl border border-border hover:bg-muted transition hover:scale-105 active:scale-95 duration-200" title={language === 'zh' ? '刷新列表' : 'Refresh List'}>
              <RefreshCw className={`w-4 h-4 text-muted-foreground ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
          {/* Stats Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            {[
              { label: t('status_waiting'), count: statusCounts.waiting, color: 'bg-yellow-50 text-yellow-700', icon: Clock },
              { label: t('status_ready'), count: statusCounts.ready, color: 'bg-blue-50 text-blue-700', icon: Clock },
              { label: t('status_in_progress'), count: statusCounts.in_progress, color: 'bg-purple-50 text-purple-700', icon: Wrench },
              { label: t('status_completed'), count: statusCounts.completed, color: 'bg-green-50 text-green-700', icon: CheckCircle },
            ].map(({ label, count, color, icon: Icon }) => (
              <div key={label} className={`rounded-2xl p-4 ${color} flex flex-col items-center`}>
                <Icon className="w-5 h-5 mb-1" />
                <span className="text-2xl font-bold">{count}</span>
                <span className="text-xs font-medium">{label}</span>
              </div>
            ))}
          </div>

          <div className="flex gap-2 flex-wrap mb-4" role="tablist" aria-label={language === 'zh' ? '按工单状态筛选' : 'Filter tasks by status'}>
            {([
              ['waiting', language === 'zh' ? '待接单' : 'Waiting'],
              ['ready', language === 'zh' ? '已接单' : 'Accepted'],
              ['in_progress', language === 'zh' ? '维修中' : 'In Progress'],
              ['completed', language === 'zh' ? '已完成' : 'Completed'],
            ] as const).map(([status, label]) => (
              <button
                key={status}
                type="button"
                role="tab"
                aria-selected={taskStatusFilter === status}
                onClick={() => { setTasksPage(1); setTaskStatusFilter(status); }}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                  taskStatusFilter === status ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground hover:bg-muted/80'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <RefreshCw className="w-6 h-6 text-muted-foreground animate-spin" />
        </div>
      ) : filteredTasks.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <Wrench className="w-12 h-12 text-muted-foreground mb-3" />
          <p className="text-muted-foreground">{language === 'zh' ? '该状态下暂无工单' : 'No tasks in this status'}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredTasks.map((task) => (
            <div key={task.id} className="bg-white rounded-2xl shadow-sm border border-border p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0 cursor-pointer" onClick={() => setDetailTarget(task)}>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-foreground">{formatRepairLocation(task.dormBuilding, task.dormFloor, task.dormRoom)}</span>
                    <Badge label={tCat(task.category || 'other', t)} colorClass="bg-gray-100 text-gray-700" />
                    {task.priority && <Badge label={tPriority(task.priority, t)} colorClass={PRIORITY_COLOR[task.priority]} />}
                  </div>
                  <p className="text-sm text-muted-foreground mt-1 line-clamp-2">{task.description}</p>
                  {task.userName && <p className="text-xs text-muted-foreground mt-1">{language === 'zh' ? `报修用户：${task.userName}` : `User: ${task.userName}`}</p>}
                  {task.userPhone && (
                    <p className="text-xs text-muted-foreground mt-1">
                      {language === 'zh' ? '报修人电话：' : 'Student phone: '}
                      {task.userPhone.includes('*') ? task.userPhone : (
                        <a href={`tel:${task.userPhone}`} onClick={(event) => event.stopPropagation()} className="text-primary hover:underline">
                          {task.userPhone}
                        </a>
                      )}
                    </p>
                  )}
                </div>
                <div className="flex flex-col items-end gap-1.5 shrink-0">
                  <Badge label={tStatus(task.status, t)} colorClass={STATUS_COLOR[task.status]} />
                  <SlaBadge slaDueDate={task.slaDueDate} status={task.status} />
                </div>
              </div>
              {task.adminNote && (
                <div className="mt-3 pt-3 border-t border-border">
                  <p className="text-xs text-muted-foreground">管理员备注：{task.adminNote}</p>
                </div>
              )}
              {task.workNote && (
                <div className="mt-3 pt-3 border-t border-border">
                  <p className="text-xs text-muted-foreground">维修记录：{task.workNote}</p>
                </div>
              )}
              {/* 评价信息显示（只读） */}
              {task.rating && task.rating > 0 && (
                <div className="mt-3 pt-3 border-t border-border bg-yellow-50/50 -mx-4 px-4 pb-1 rounded-b-2xl">
                  <p className="text-xs font-medium text-foreground mb-1">⭐ 用户评价</p>
                  <div className="flex items-center gap-1 mb-1">
                    {[1,2,3,4,5].map((s) => (
                      <Star key={s} className={`w-4 h-4 ${s <= task.rating! ? 'text-yellow-400 fill-current' : 'text-gray-200'}`} />
                    ))}
                  </div>
                </div>
              )}
              <div className="mt-3 pt-3 border-t border-border">
                {selected?.id === task.id ? (
                  <div className="space-y-3">
                    {task.status !== 'rejected' && task.status !== 'pending_evaluation' && task.status !== 'closed' && (
                      <>
                        {/* 暂时隐藏维修记录输入，提交完成时由 updateTask 传默认值。
                        {task.status === 'in_progress' && <textarea value={workNote} onChange={(e) => setWorkNote(e.target.value)}
                          rows={2} placeholder="填写维修记录（必填，至少5个字）"
                          className="w-full px-3 py-2 rounded-xl border border-border bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 text-sm resize-none" />}
                        */}

                        {/* 暂时隐藏备件选择器，保留代码以便后续恢复。
                        {task.status === 'in_progress' && <div className="bg-muted/30 border border-border rounded-xl p-3">
                          <p className="text-xs font-semibold text-foreground mb-2 flex items-center gap-1">
                            <Wrench className="w-3.5 h-3.5 text-primary" />
                            登记消耗配件物料（完工时生效，可选）
                          </p>
                          {inventoryParts.length === 0 ? (
                            <p className="text-xs text-muted-foreground text-center py-2">无库存配件备件可用</p>
                          ) : (
                            <div className="space-y-2 max-h-40 overflow-y-auto pr-1">
                              {inventoryParts.map((part) => {
                                const currentQty = selectedParts[part.id] || 0;
                                return (
                                  <div key={part.id} className="flex items-center justify-between text-xs">
                                    <div className="flex flex-col">
                                      <span className="font-medium">{part.name}</span>
                                      <span className="text-[10px] text-muted-foreground">单价: ￥{part.price.toFixed(2)} | 库存: {part.stock}</span>
                                    </div>
                                    <div className="flex items-center gap-1.5">
                                      <button
                                        type="button"
                                        onClick={() => {
                                          if (currentQty > 0) {
                                            setSelectedParts(p => ({ ...p, [part.id]: currentQty - 1 }));
                                          }
                                        }}
                                        disabled={currentQty === 0}
                                        className="w-5 h-5 rounded border border-border flex items-center justify-center bg-white hover:bg-muted font-bold disabled:opacity-50 select-none"
                                      >
                                        -
                                      </button>
                                      <span className="w-5 text-center font-bold text-foreground">{currentQty}</span>
                                      <button
                                        type="button"
                                        onClick={() => {
                                          if (currentQty < part.stock) {
                                            setSelectedParts(p => ({ ...p, [part.id]: currentQty + 1 }));
                                          } else {
                                            toast.error(`不能超过库存剩余数量 (${part.stock})`);
                                          }
                                        }}
                                        disabled={part.stock === 0}
                                        className="w-5 h-5 rounded border border-border flex items-center justify-center bg-white hover:bg-muted font-bold disabled:opacity-50 select-none"
                                      >
                                        +
                                      </button>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>}
                        */}

                        <div className="flex gap-2">
                          <button onClick={() => { setSelected(null); setWorkNote(''); setSelectedParts({}); }}
                            className="flex-1 py-2 rounded-xl border border-border text-foreground text-sm hover:bg-muted transition">{t('cancel')}</button>
                          {task.status === 'waiting' && (
                            <button onClick={() => updateTask(task.id, 'ready')} disabled={updating}
                              className="flex-1 py-2 bg-blue-600 text-white rounded-xl text-sm font-medium hover:opacity-90 transition disabled:opacity-50">
                              {updating ? '...' : (language === 'zh' ? '接单' : 'Accept Task')}
                            </button>
                          )}
                          {task.status === 'ready' && (
                            <button onClick={() => updateTask(task.id, 'in_progress')} disabled={updating}
                              className="flex-1 py-2 bg-purple-600 text-white rounded-xl text-sm font-medium hover:opacity-90 transition disabled:opacity-50">
                              {updating ? '...' : (language === 'zh' ? '到场，开始维修' : 'Start Repair')}
                            </button>
                          )}
                          {task.status === 'in_progress' && <button onClick={() => updateTask(task.id, 'completed')} disabled={updating}
                            className="flex-1 py-2 bg-green-600 text-white rounded-xl text-sm font-medium hover:opacity-90 transition disabled:opacity-50">
                            {updating ? '...' : (language === 'zh' ? '提交维修完成' : t('completeRepair'))}
                          </button>}
                        </div>
                      </>
                    )}
                    {/* 暂时隐藏物料消耗展示，保留代码以便后续恢复。
                    <ConsumedPartsList repairId={task.id} token={token} status={task.status} />
                    */}
                    <button onClick={() => { setSelected(null); setWorkNote(''); setSelectedParts({}); }}
                      className="w-full py-2 rounded-xl border border-border text-foreground text-sm hover:bg-muted transition mt-2">
                      {language === 'zh' ? '收起' : 'Collapse'}
                    </button>
                  </div>

                ) : task.status === 'waiting' ? (
                  <button onClick={() => updateTask(task.id, 'ready')} disabled={updating}
                    className="w-full py-2 rounded-xl border border-primary bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 transition disabled:opacity-50">
                    {updating ? '...' : (language === 'zh' ? '接单' : 'Accept Task')}
                  </button>
                ) : task.status === 'ready' ? (
                  <button onClick={() => updateTask(task.id, 'in_progress')} disabled={updating}
                    className="w-full py-2 rounded-xl border border-primary bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 transition disabled:opacity-50">
                    {updating ? '...' : (language === 'zh' ? '开始维修' : 'Start Repair')}
                  </button>
                ) : task.status === 'in_progress' ? (
                  <button onClick={() => updateTask(task.id, 'completed')} disabled={updating}
                    className="w-full py-2 rounded-xl border border-green-600 bg-green-600 text-white text-sm font-medium hover:opacity-90 transition disabled:opacity-50">
                    {updating ? '...' : (language === 'zh' ? '维修完成' : 'Complete Repair')}
                  </button>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      )}
      <Pagination currentPage={tasksPage} totalCount={tasksTotal} pageSize={tasksPageSize} onPageChange={setTasksPage} />
        </>
      )}

      {tab === 'stats' && (
        <div className="space-y-6">
          <div className="bg-white rounded-2xl shadow-sm border border-border p-6">
            <h3 className="text-lg font-bold text-foreground mb-6">{language === 'zh' ? '绩效概览' : 'Performance Overview'}</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div className="bg-blue-50 text-blue-700 rounded-2xl p-4 flex flex-col">
                <span className="text-xs font-medium mb-1">{language === 'zh' ? '总任务数' : 'Total Tasks'}</span>
                <span className="text-3xl font-bold">{statusCounts.totalAssigned}</span>
              </div>
              <div className="bg-green-50 text-green-700 rounded-2xl p-4 flex flex-col">
                <span className="text-xs font-medium mb-1">{language === 'zh' ? '已完成任务' : 'Completed Tasks'}</span>
                <span className="text-3xl font-bold">{statusCounts.completed}</span>
              </div>
              <div className="bg-yellow-50 text-yellow-700 rounded-2xl p-4 flex flex-col">
                <span className="text-xs font-medium mb-1">{language === 'zh' ? '待接单任务' : 'Waiting Tasks'}</span>
                <span className="text-3xl font-bold">{pending}</span>
              </div>
              <div className="bg-blue-50 text-blue-700 rounded-2xl p-4 flex flex-col">
                <span className="text-xs font-medium mb-1">{t('status_ready')}</span>
                <span className="text-3xl font-bold">{ready}</span>
              </div>
              <div className="bg-purple-50 text-purple-700 rounded-2xl p-4 flex flex-col">
                <span className="text-xs font-medium mb-1">{language === 'zh' ? '进行中任务' : 'In Progress Tasks'}</span>
                <span className="text-3xl font-bold">{inProgress}</span>
              </div>
            </div>

            <div className="bg-muted/30 rounded-2xl p-6 border border-border flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground mb-1">{language === 'zh' ? '平均服务评分' : 'Average Service Rating'}</p>
                <div className="flex items-end gap-3">
                  <span className="text-4xl font-extrabold text-foreground">{avgRating === '暂无' && language !== 'zh' ? 'None' : avgRating}</span>
                  <span className="text-sm text-muted-foreground mb-1.5">/ 5.0</span>
                </div>
              </div>
              <div className="flex gap-1">
                {[1, 2, 3, 4, 5].map((s) => (
                  <Star key={s} className={`w-8 h-8 ${avgRating !== '暂无' && s <= Math.round(Number(avgRating)) ? 'text-yellow-400 fill-yellow-400' : 'text-gray-200'}`} />
                ))}
              </div>
            </div>

            <p className="text-xs text-muted-foreground mt-4 text-center">{language === 'zh' ? '以上数据根据您分配的维修任务本地计算得出。' : 'The above data is calculated locally based on your assigned tasks.'}</p>
          </div>
        </div>
      )}
      <RepairDetailModal repair={detailTarget} token={token} onClose={() => setDetailTarget(null)} />
    </div>
  );
}
