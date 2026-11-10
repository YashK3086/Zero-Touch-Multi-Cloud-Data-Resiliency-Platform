import React, { useState, useEffect } from 'react';
import {
  Server,
  Cpu,
  Layers,
  ArrowRight,
  Zap,
  CheckCircle2,
  Clock,
  RefreshCw,
  ExternalLink,
  ShieldCheck,
  AlertCircle,
  Database,
  HardDrive,
  Copy,
  Sparkles,
  GitBranch,
  Radio,
} from 'lucide-react';

export default function WorkloadHydrationMatrix() {
  const [workloadsData, setWorkloadsData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [hydrating, setHydrating] = useState(false);
  const [probeResult, setProbeResult] = useState(null);
  const [probing, setProbing] = useState(false);
  const [activeTab, setActiveTab] = useState('resources'); // 'resources' | 'storage' | 'blueprint' | 'workloads'

  const fetchWorkloads = async () => {
    try {
      setLoading(true);
      const res = await fetch('/api/workloads/live');
      if (res.ok) {
        const data = await res.json();
        setWorkloadsData(data);
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkloads();
    const interval = setInterval(fetchWorkloads, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleManualHydrate = async () => {
    try {
      setHydrating(true);
      const res = await fetch('/api/workloads/hydrate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_replicas: 1 }),
      });
      if (res.ok) {
        await fetchWorkloads();
      }
    } catch {
      // ignore
    } finally {
      setHydrating(false);
    }
  };

  const handleProbeSynthetic = async () => {
    try {
      setProbing(true);
      const res = await fetch('/api/workloads/probe-synthetic', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setProbeResult(data);
      }
    } catch {
      // ignore
    } finally {
      setProbing(false);
    }
  };

  const workloads = workloadsData?.workloads || [];
  const isAzureActive = workloadsData?.active_cloud?.toUpperCase() === 'AZURE';
  const compute = workloadsData?.current_compute;
  const storage = workloadsData?.current_storage;
  const blueprint = workloadsData?.controller_blueprint;

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs mb-6 max-w-full overflow-hidden">
      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-slate-100">
        <div className="flex items-center space-x-3 min-w-0">
          <div className="w-10 h-10 rounded-lg bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-600 shadow-xs shrink-0">
            <Layers className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center space-x-2 flex-wrap gap-y-1">
              <h2 className="text-sm font-black text-slate-900 tracking-tight uppercase truncate">
                Live Cloud Resources & 1:1 Replicability Engine
              </h2>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold tracking-wide uppercase bg-emerald-50 text-emerald-700 border border-emerald-200 shrink-0">
                Pilot-Light ($0 Idle Compute)
              </span>
              {workloadsData?.has_hosted_data ? (
                <span className="px-2 py-0.5 rounded text-[10px] font-bold tracking-wide uppercase bg-blue-50 text-blue-700 border border-blue-200 shrink-0">
                  1:1 Azure Snapshot Armed
                </span>
              ) : (
                <span className="px-2 py-0.5 rounded text-[10px] font-bold tracking-wide uppercase bg-slate-100 text-slate-600 border border-slate-200 shrink-0">
                  0 Workloads Hosted (Scanning Cloud)
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500 font-medium truncate">
              Continuous live discovery of running compute, hosted storage, and automated failover replication
            </p>
          </div>
        </div>

        {/* View Switcher Tabs */}
        <div className="flex items-center space-x-1 bg-slate-100 p-1 rounded-lg border border-slate-200 text-xs font-bold shrink-0">
          <button
            onClick={() => setActiveTab('resources')}
            className={`px-3 py-1 rounded-md transition cursor-pointer flex items-center space-x-1.5 ${
              activeTab === 'resources' ? 'bg-white text-indigo-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Cpu className="w-3.5 h-3.5" />
            <span>Current Compute</span>
          </button>
          <button
            onClick={() => setActiveTab('storage')}
            className={`px-3 py-1 rounded-md transition cursor-pointer flex items-center space-x-1.5 ${
              activeTab === 'storage' ? 'bg-white text-emerald-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <HardDrive className="w-3.5 h-3.5" />
            <span>Current Storage Hosted</span>
          </button>
          <button
            onClick={() => setActiveTab('blueprint')}
            className={`px-3 py-1 rounded-md transition cursor-pointer flex items-center space-x-1.5 ${
              activeTab === 'blueprint' ? 'bg-white text-blue-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>1:1 Failover Blueprint</span>
          </button>
          <button
            onClick={() => setActiveTab('workloads')}
            className={`px-3 py-1 rounded-md transition cursor-pointer flex items-center space-x-1.5 ${
              activeTab === 'workloads' ? 'bg-white text-amber-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Server className="w-3.5 h-3.5" />
            <span>Microservices ({workloads.length})</span>
          </button>
        </div>
      </div>

      {/* Synthetic Probe Banner */}
      {probeResult && (
        <div className="mt-3 p-3 rounded-lg bg-slate-900 text-slate-100 flex flex-wrap items-center justify-between text-xs font-mono gap-2">
          <div className="flex items-center space-x-2 min-w-0">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shrink-0"></span>
            <span className="text-emerald-400 font-bold shrink-0">SYNTHETIC PROBE:</span>
            <span className="truncate">{probeResult.probe_target}</span>
          </div>
          <div className="flex items-center space-x-3 text-slate-400 shrink-0">
            <span>Latency: <strong className="text-amber-300">{probeResult.latency_ms}ms</strong></span>
            <span>Status: <strong className="text-emerald-300">{probeResult.http_status} OK</strong></span>
          </div>
        </div>
      )}

      {/* TAB 1: CURRENT COMPUTE HOSTED */}
      {activeTab === 'resources' && (
        <div className="mt-4 space-y-4 min-w-0">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Primary / Active AWS Compute */}
            <div className={`p-4 rounded-xl border space-y-3 min-w-0 transition ${
              !isAzureActive
                ? 'border-emerald-300 bg-emerald-50/20'
                : 'border-slate-200 bg-slate-50/40'
            }`}>
              <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                <div className="flex items-center space-x-2">
                  <span className={`w-2.5 h-2.5 rounded-full ${!isAzureActive ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'}`}></span>
                  <span className="text-xs font-black text-slate-900 uppercase tracking-wider">
                    {!isAzureActive ? 'Primary Compute' : 'Standby Compute Replica'} (AWS · {compute?.primary?.region || 'us-east-1'})
                  </span>
                </div>
                <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${
                  !isAzureActive
                    ? 'bg-emerald-100 text-emerald-800 border-emerald-300'
                    : 'bg-slate-100 text-slate-700 border-slate-300'
                }`}>
                  {compute?.primary?.status_badge || (!isAzureActive ? '0 RUNNING (PRIMARY)' : '0 RUNNING (STANDBY REPLICA)')}
                </span>
              </div>

              <div className="space-y-2 text-xs">
                <div className="flex justify-between items-center py-1 border-b border-slate-100">
                  <span className="text-slate-500 font-medium">Running EC2 Instances:</span>
                  <span className="font-mono font-black text-slate-900">
                    {compute?.primary?.running_instances ?? 0} Running
                  </span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-slate-100">
                  <span className="text-slate-500 font-medium">Instance ID:</span>
                  <span className="font-mono text-slate-800 truncate max-w-[200px]" title={compute?.primary?.instance_id}>
                    {compute?.primary?.instance_id || '0 Running'}
                  </span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-slate-100">
                  <span className="text-slate-500 font-medium">VPC Network:</span>
                  <span className="font-mono text-slate-700 truncate max-w-[200px]" title={compute?.primary?.vpc_id}>
                    {compute?.primary?.vpc_id || 'None (0 Deployed)'}
                  </span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-slate-100">
                  <span className="text-slate-500 font-medium">Public IP & Ingress:</span>
                  <span className="font-mono text-blue-700 truncate max-w-[200px]" title={compute?.primary?.public_ip}>
                    {compute?.primary?.public_ip || 'None (0 Running)'}
                  </span>
                </div>
                <div className="flex justify-between items-center py-1">
                  <span className="text-slate-500 font-medium">Snowflake Compute Warehouse:</span>
                  <span className="font-mono text-emerald-700 font-bold">
                    {compute?.primary?.warehouse || 'DR_CONTROLLER_WH'}
                  </span>
                </div>
              </div>
            </div>

            {/* Azure Compute */}
            <div className={`p-4 rounded-xl border space-y-3 min-w-0 transition ${
              isAzureActive
                ? 'border-emerald-400 bg-emerald-50/25 shadow-xs'
                : 'border-sky-200 bg-sky-50/20'
            }`}>
              <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                <div className="flex items-center space-x-2">
                  <span className={`w-2.5 h-2.5 rounded-full ${isAzureActive ? 'bg-emerald-500 animate-pulse' : 'bg-blue-500'}`}></span>
                  <span className="text-xs font-black text-slate-900 uppercase tracking-wider">
                    {isAzureActive ? 'Active Primary Compute' : 'Standby Compute'} (Azure · {compute?.secondary?.region || 'East US 2'})
                  </span>
                </div>
                <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${
                  isAzureActive
                    ? 'bg-emerald-600 text-white border-emerald-700'
                    : 'bg-sky-100 text-sky-800 border-sky-300'
                }`}>
                  {compute?.secondary?.status_badge || (isAzureActive ? 'PRIMARY (ACTIVE PROMOTED)' : '0 RUNNING (PILOT-LIGHT)')}
                </span>
              </div>

              <div className="space-y-2 text-xs">
                <div className="flex justify-between items-center py-1 border-b border-slate-100">
                  <span className="text-slate-500 font-medium">Azure Container App Replicas:</span>
                  <span className="font-mono font-black text-slate-900">
                    {compute?.secondary?.running_instances ?? 0} Active Replicas ($0.00 Idle Cost)
                  </span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-slate-100">
                  <span className="text-slate-500 font-medium">Resource Group:</span>
                  <span className="font-mono text-slate-800 truncate max-w-[200px]" title={compute?.secondary?.active_resource_group}>
                    {compute?.secondary?.active_resource_group || 'rg-sf-dr-drdemo'}
                  </span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-slate-100">
                  <span className="text-slate-500 font-medium">Failover Replica Target:</span>
                  <span className="font-mono text-indigo-700 truncate max-w-[200px]" title={compute?.secondary?.replica_service}>
                    {compute?.secondary?.replica_service || 'paysecure-api-dr'}
                  </span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-slate-100">
                  <span className="text-slate-500 font-medium">Hydration Latency SLA:</span>
                  <span className="font-mono text-emerald-700 font-bold">
                    &lt; 8.2s Instant Spin-up on Failover
                  </span>
                </div>
                <div className="flex justify-between items-center py-1">
                  <span className="text-slate-500 font-medium">Snowflake Compute Warehouse:</span>
                  <span className="font-mono text-emerald-700 font-bold">
                    {compute?.secondary?.warehouse || 'DR_CONTROLLER_WH'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: CURRENT STORAGE HOSTED */}
      {activeTab === 'storage' && (
        <div className="mt-4 space-y-4 min-w-0">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Primary / AWS Storage */}
            <div className={`p-4 rounded-xl border space-y-3 min-w-0 transition ${
              !isAzureActive
                ? 'border-emerald-300 bg-emerald-50/20'
                : 'border-slate-200 bg-slate-50/40'
            }`}>
              <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                <div className="flex items-center space-x-2">
                  <HardDrive className={`w-4 h-4 ${!isAzureActive ? 'text-emerald-600' : 'text-slate-400'}`} />
                  <span className="text-xs font-black text-slate-900 uppercase tracking-wider">
                    {!isAzureActive ? 'Primary Data & Storage' : 'Standby Replica Storage'} ({storage?.primary?.cloud || 'AWS S3 + Snowflake'})
                  </span>
                </div>
                <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${
                  !isAzureActive
                    ? 'bg-emerald-100 text-emerald-800 border-emerald-300'
                    : 'bg-slate-100 text-slate-700 border-slate-300'
                }`}>
                  {storage?.primary?.status_badge || (!isAzureActive ? 'ACTIVE PRIMARY (R/W)' : 'STANDBY REPLICA (R/O)')}
                </span>
              </div>

              <div className="space-y-2 text-xs">
                <div className="flex justify-between items-center py-1 border-b border-slate-100">
                  <span className="text-slate-500 font-medium">Hosted App Storage (S3/RDS/EFS):</span>
                  <span className="font-mono font-bold text-slate-900 truncate max-w-[230px]" title={storage?.primary?.app_storage}>
                    {storage?.primary?.app_storage || '0 App Buckets · 0 RDS · 0 EFS'}
                  </span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-slate-100">
                  <span className="text-slate-500 font-medium">Detected Data Location:</span>
                  <span className="font-mono text-blue-700 truncate max-w-[230px]" title={storage?.primary?.data_location}>
                    {storage?.primary?.data_location || 'None — No Application Data Hosted Yet'}
                  </span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-slate-100">
                  <span className="text-slate-500 font-medium">DR Throw Bridge Bucket:</span>
                  <span className="font-mono text-slate-800 truncate max-w-[230px]" title={storage?.primary?.throw_uri}>
                    {storage?.primary?.throw_uri || '--'}
                  </span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-slate-100">
                  <span className="text-slate-500 font-medium">Staged Dataset Files:</span>
                  <span className="font-mono text-slate-800 font-bold">
                    {storage?.primary?.staged_files_label || '0 Staged Files (No Hosted App Data)'}
                  </span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-slate-100">
                  <span className="text-slate-500 font-medium">Snowpipe Ingestion Status:</span>
                  <span className="font-mono text-indigo-700 truncate max-w-[230px]" title={storage?.primary?.snowpipe}>
                    {storage?.primary?.snowpipe || 'Idle — Awaiting Hosted App Data'}
                  </span>
                </div>
                <div className="flex justify-between items-center py-1">
                  <span className="text-slate-500 font-medium">Hosted Database Rows:</span>
                  <span className="font-mono text-emerald-800 font-bold">
                    {storage?.primary?.hosted_rows != null ? `${storage.primary.hosted_rows.toLocaleString()} rows` : '0 rows'}
                  </span>
                </div>
              </div>
            </div>

            {/* Standby / Azure Storage */}
            <div className={`p-4 rounded-xl border space-y-3 min-w-0 transition ${
              isAzureActive
                ? 'border-emerald-400 bg-emerald-50/25 shadow-xs'
                : 'border-sky-200 bg-sky-50/20'
            }`}>
              <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                <div className="flex items-center space-x-2">
                  <Database className={`w-4 h-4 ${isAzureActive ? 'text-emerald-600' : 'text-sky-600'}`} />
                  <span className="text-xs font-black text-slate-900 uppercase tracking-wider">
                    {isAzureActive ? 'Active Primary Storage' : 'Standby Catch Storage'} ({storage?.secondary?.cloud || 'Azure Blob + Snowflake Replica'})
                  </span>
                </div>
                <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${
                  isAzureActive
                    ? 'bg-emerald-600 text-white border-emerald-700'
                    : 'bg-sky-100 text-sky-800 border-sky-300'
                }`}>
                  {storage?.secondary?.status_badge || (isAzureActive ? 'ACTIVE PRIMARY (R/W)' : '0 REPLICA DATA (DR BLOB READY)')}
                </span>
              </div>

              <div className="space-y-2 text-xs">
                <div className="flex justify-between items-center py-1 border-b border-slate-100">
                  <span className="text-slate-500 font-medium">Replicated App Storage:</span>
                  <span className="font-mono font-bold text-slate-900 truncate max-w-[230px]" title={storage?.secondary?.replicated_app_storage}>
                    {storage?.secondary?.replicated_app_storage || 'None — Awaiting Primary Data Discovery'}
                  </span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-slate-100">
                  <span className="text-slate-500 font-medium">DR Catch Storage Account:</span>
                  <span className="font-mono font-bold text-slate-900 truncate max-w-[220px]" title={storage?.secondary?.catch_storage_account}>
                    {storage?.secondary?.catch_storage_account || '--'}
                  </span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-slate-100">
                  <span className="text-slate-500 font-medium">Catch Blob Container:</span>
                  <span className="font-mono text-blue-700 truncate max-w-[220px]" title={storage?.secondary?.catch_uri}>
                    {storage?.secondary?.catch_uri || '--'}
                  </span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-slate-100">
                  <span className="text-slate-500 font-medium">Replica Rows:</span>
                  <span className="font-mono font-bold text-slate-900">
                    {storage?.secondary?.hosted_rows != null ? `${storage.secondary.hosted_rows.toLocaleString()} rows` : '0 rows'}
                  </span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-slate-100">
                  <span className="text-slate-500 font-medium">Cross-Cloud RPO Delta:</span>
                  <span className="font-mono text-emerald-700 font-bold">
                    {storage?.secondary?.rpo_delta === 0 ? '0 Rows (Zero Data Loss)' : `${storage?.secondary?.rpo_delta} pending`}
                  </span>
                </div>
                <div className="flex justify-between items-center py-1">
                  <span className="text-slate-500 font-medium">Snowflake Account:</span>
                  <span className="font-mono text-slate-800 truncate max-w-[200px]" title={storage?.secondary?.snowflake_account}>
                    {storage?.secondary?.snowflake_account || '--'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: 1:1 FAILOVER BLUEPRINT (EXACT REPLICA SPIN-UP) */}
      {activeTab === 'blueprint' && (
        <div className="mt-4 p-5 rounded-xl border border-indigo-200 bg-gradient-to-r from-indigo-50/50 via-slate-50 to-indigo-50/30 space-y-4 min-w-0">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-indigo-100 pb-3">
            <div className="flex items-center space-x-2">
              <Sparkles className="w-5 h-5 text-indigo-600 shrink-0" />
              <div>
                <h3 className="text-xs font-black text-indigo-950 uppercase tracking-wider">
                  Controller 1:1 Live Snapshot & Disaster Replication Engine
                </h3>
                <p className="text-[11px] text-slate-500">
                  Upon failover trigger, Azure spins up an identical production mirror in seconds
                </p>
              </div>
            </div>
            <span className="px-2.5 py-1 rounded-md text-[10px] font-mono font-black bg-indigo-600 text-white shadow-xs">
              {blueprint?.state || 'ARMED & SYNCHRONIZED'}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs font-mono">
            <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-2xs">
              <span className="text-[10px] font-bold text-slate-400 block uppercase">Active Traffic Leader</span>
              <span className="text-slate-900 font-bold">
                {isAzureActive ? 'Azure East US 2 (AZURE)' : `${blueprint?.active_authority || 'AWS'} (us-east-1)`}
              </span>
            </div>
            <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-2xs">
              <span className="text-[10px] font-bold text-slate-400 block uppercase">Global Redirect DNS</span>
              <span className="text-blue-700 font-bold truncate block" title={blueprint?.global_anycast_dns}>
                {blueprint?.global_anycast_dns || 'nnfcdxy-sf_dr_global_redirect'}
              </span>
            </div>
            <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-2xs">
              <span className="text-[10px] font-bold text-slate-400 block uppercase">Replication Schedule</span>
              <span className="text-emerald-700 font-bold">{blueprint?.replication_schedule || '10 MINUTE + Instant'}</span>
            </div>
          </div>

          <div className="p-4 bg-white rounded-lg border border-slate-200 space-y-2">
            <span className="text-xs font-bold text-slate-900 flex items-center space-x-1.5">
              <GitBranch className="w-4 h-4 text-indigo-600" />
              <span>Autonomous Switchover Execution Steps (0 Downtime):</span>
            </span>
            <div className="space-y-1.5 text-xs text-slate-700 font-mono">
              {(blueprint?.what_happens_on_failover || []).map((step, idx) => (
                <div key={idx} className="p-2 rounded bg-slate-50 border border-slate-100 flex items-start space-x-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <span className="leading-relaxed">{step}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: MICROSERVICE WORKLOADS (COMPLETELY CONSTRAINED & NON-OVERFLOWING) */}
      {activeTab === 'workloads' && (
        <div className="grid grid-cols-1 gap-3.5 mt-4 min-w-0">
          {workloads.length === 0 ? (
            <div className="p-6 rounded-xl border border-dashed border-slate-300 bg-slate-50 text-center text-xs text-slate-500 font-medium">
              {workloadsData?.connected
                ? '-- 0 Running Microservices Discovered on Primary Cloud (AWS). Continuous 5s probe is scanning EC2, ECS, and VPCs — deploy your service to auto-populate --'
                : "-- No connections or workload blueprints available yet. Click 'Connect Accounts' to activate pilot-light hydration --"}
            </div>
          ) : (
            workloads.map((wl) => (
              <div
                key={wl.name}
                className="p-4 rounded-xl border border-slate-200 bg-slate-50/60 hover:bg-white transition grid grid-cols-1 lg:grid-cols-12 gap-3.5 items-stretch min-w-0"
              >
                {/* 1. Service Info (Col 3) */}
                <div className="lg:col-span-3 min-w-0 flex flex-col justify-between p-1">
                  <div className="flex items-center space-x-2.5 min-w-0">
                    <div className="w-9 h-9 rounded-lg bg-white border border-slate-200 flex items-center justify-center text-slate-700 shadow-2xs shrink-0">
                      <Server className="w-4 h-4" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center space-x-1.5 min-w-0">
                        <span className="text-xs font-black text-slate-900 tracking-tight truncate">{wl.name}</span>
                        <span className="px-1.5 py-0.2 rounded text-[10px] font-mono text-slate-500 bg-slate-200 shrink-0">
                          v{wl.version}
                        </span>
                      </div>
                      <p className="text-[10px] text-slate-500 truncate" title={wl.description}>
                        {wl.description}
                      </p>
                    </div>
                  </div>
                  <div className="text-[10px] text-slate-500 font-mono flex items-center space-x-2 mt-2 pt-2 border-t border-slate-200/60">
                    <span>Port: {wl.port}</span>
                    <span>·</span>
                    <span>CPU: {wl.resources?.cpu}</span>
                    <span>·</span>
                    <span>RAM: {wl.resources?.memory}</span>
                  </div>
                </div>

                {/* 2. Primary / Standby AWS Card (Col 4) */}
                <div className={`lg:col-span-4 min-w-0 overflow-hidden p-3 rounded-lg border text-xs transition ${
                  !isAzureActive
                    ? 'bg-emerald-50/80 border-emerald-300 text-emerald-950'
                    : 'bg-slate-50/70 border-slate-200 text-slate-600'
                }`}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="font-bold flex items-center space-x-1.5 min-w-0">
                      <span className={`w-2 h-2 rounded-full shrink-0 ${!isAzureActive ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'}`}></span>
                      <span className="truncate">{!isAzureActive ? 'Primary' : 'Standby Replica'} ({wl.aws?.cloud || 'AWS'} · {wl.aws?.region || 'us-east-1'})</span>
                    </span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-black uppercase shrink-0 ${
                      !isAzureActive ? 'bg-emerald-200 text-emerald-900' : 'bg-slate-100 text-slate-600 border border-slate-200'
                    }`}>
                      {!isAzureActive
                        ? (wl.aws?.replicas > 0 ? `${wl.aws.replicas} REPL ACTIVE` : '0 REPL (PRIMARY)')
                        : '0 REPL (STANDBY)'}
                    </span>
                  </div>
                  <div className="text-[11px] font-mono space-y-0.5">
                    <div className="truncate text-slate-700" title={wl.aws?.instance_id}>
                      Compute: <strong className="text-slate-900">{wl.aws?.instance_id}</strong>
                    </div>
                    <div className="truncate text-slate-600" title={wl.aws?.vpc_id}>
                      VPC: <strong className="text-slate-800">{wl.aws?.vpc_id}</strong>
                    </div>
                    <div className="truncate text-blue-700" title={wl.aws?.public_ip}>
                      Public IP: <strong>{wl.aws?.public_ip}</strong>
                    </div>
                  </div>
                </div>

                {/* 3. Cross-cloud Direction Arrow (Col 1) */}
                <div className="lg:col-span-1 hidden lg:flex items-center justify-center text-slate-300">
                  <ArrowRight className={`w-5 h-5 transition-transform ${isAzureActive ? 'rotate-180 text-emerald-500' : ''}`} />
                </div>

                {/* 4. Standby / Active Primary Azure Card (Col 4) */}
                <div className={`lg:col-span-4 min-w-0 overflow-hidden p-3 rounded-lg border text-xs transition ${
                  isAzureActive
                    ? 'bg-emerald-50/80 border-emerald-400 text-emerald-950 shadow-xs'
                    : 'bg-white border-slate-200 text-slate-600'
                }`}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="font-bold flex items-center space-x-1.5 min-w-0">
                      <span className={`w-2 h-2 rounded-full shrink-0 ${isAzureActive ? 'bg-emerald-500 animate-pulse' : 'bg-blue-500'}`}></span>
                      <span className="truncate">{isAzureActive ? 'Active Primary' : 'Standby'} ({wl.azure?.cloud || 'Azure'} · {wl.azure?.region || 'East US 2'})</span>
                    </span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-black uppercase shrink-0 ${
                      isAzureActive ? 'bg-emerald-600 text-white' : 'bg-sky-100 text-sky-800 border border-sky-200'
                    }`}>
                      {isAzureActive ? 'ACTIVE PRIMARY' : 'PILOT-LIGHT (0 REPL)'}
                    </span>
                  </div>
                  <div className="text-[11px] font-mono space-y-0.5">
                    <div className="truncate text-slate-700" title={wl.azure?.resource_group}>
                      RG: <strong className="text-slate-900">{wl.azure?.resource_group || '--'}</strong>
                    </div>
                    <div className="truncate text-slate-600" title={wl.azure?.app_name}>
                      Replica: <strong className="text-slate-800">{wl.azure?.app_name}</strong>
                    </div>
                    <div className="truncate text-indigo-700" title={wl.azure?.ingress_url}>
                      Ingress: <strong>{wl.azure?.ingress_url}</strong>
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
