import React, { useState } from 'react';
import {
  Shield,
  Server,
  Cloud,
  CheckCircle2,
  AlertCircle,
  Loader2,
  KeyRound,
  ArrowRight,
  Zap,
  X,
  Sparkles,
} from 'lucide-react';

export default function OnboardingModal({ isOpen, onClose, onSuccess }) {
  // Primary (Source) Snowflake + Cloud Provider API Credentials
  const [primaryAccount, setPrimaryAccount] = useState('');
  const [primaryUser, setPrimaryUser] = useState('');
  const [primaryPassword, setPrimaryPassword] = useState('');
  const [primaryRole] = useState('ACCOUNTADMIN');
  const [primaryCloud, setPrimaryCloud] = useState('Auto-Detect');
  const [primaryCloudRegion, setPrimaryCloudRegion] = useState('');
  const [primaryCloudAccessId, setPrimaryCloudAccessId] = useState('');
  const [primaryCloudSecretKey, setPrimaryCloudSecretKey] = useState('');
  const [databaseName, setDatabaseName] = useState('');

  // Secondary (Standby DR) Snowflake + Cloud Provider API Credentials
  const [secondaryAccount, setSecondaryAccount] = useState('');
  const [secondaryUser, setSecondaryUser] = useState('');
  const [secondaryPassword, setSecondaryPassword] = useState('');
  const [secondaryRole] = useState('ACCOUNTADMIN');
  const [secondaryCloud, setSecondaryCloud] = useState('Auto-Detect');
  const [secondaryCloudRegion, setSecondaryCloudRegion] = useState('');
  const [secondaryCloudAccessId, setSecondaryCloudAccessId] = useState('');
  const [secondaryCloudSecretKey, setSecondaryCloudSecretKey] = useState('');
  const [warehouseName, setWarehouseName] = useState('');

  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState(null);
  const [verifyError, setVerifyError] = useState(null);

  const [provisioning, setProvisioning] = useState(false);
  const [provisionStep, setProvisionStep] = useState(0);
  const [provisionError, setProvisionError] = useState(null);
  const [provisionSuccess, setProvisionSuccess] = useState(false);

  if (!isOpen) return null;

  const handleFillDemo = () => {
    setPrimaryAccount('NNFCDXY-SF_AWS_PRIMARY');
    setPrimaryUser('YASHSNOW20');
    setPrimaryPassword('Atlas20@200605');
    setPrimaryCloud('AWS');
    setPrimaryCloudRegion('us-east-1');
    setPrimaryCloudAccessId('••••••••••••••••••••');
    setPrimaryCloudSecretKey('••••••••••••••••••••••••••••••••');
    setDatabaseName('SF_DR_DEMO_DB');

    setSecondaryAccount('NNFCDXY-SF_AZURE_DR');
    setSecondaryUser('YASHSNOW20');
    setSecondaryPassword('Atlas20@200605');
    setSecondaryCloud('Azure');
    setSecondaryCloudRegion('eastus2');
    setSecondaryCloudAccessId('1fbaecf5-392d-4648-9f2e-4d694cfc0b83');
    setSecondaryCloudSecretKey('••••••••••••••••••••••••••••••••');
    setWarehouseName('DR_CONTROLLER_WH');

    setVerifyResult(null);
    setVerifyError(null);
  };

  const handleVerify = async () => {
    setVerifying(true);
    setVerifyError(null);
    setVerifyResult(null);

    try {
      const res = await fetch('/api/onboarding/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          primary_account: primaryAccount,
          primary_user: primaryUser,
          primary_password: primaryPassword,
          primary_role: primaryRole,
          secondary_account: secondaryAccount,
          secondary_user: secondaryUser,
          secondary_password: secondaryPassword,
          secondary_role: secondaryRole,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to verify account credentials');
      }
      setVerifyResult(data);

      // Dynamically set detected cloud provider & region from Snowflake handshake
      if (data?.primary?.region) {
        const parts = data.primary.region.split('_');
        if (parts[0]) setPrimaryCloud(parts[0]);
        if (parts.length > 1) setPrimaryCloudRegion(parts.slice(1).join('-').toLowerCase());
      }
      if (data?.secondary?.region) {
        const parts = data.secondary.region.split('_');
        if (parts[0]) setSecondaryCloud(parts[0]);
        if (parts.length > 1) setSecondaryCloudRegion(parts.slice(1).join('-').toLowerCase());
      }
    } catch (err) {
      setVerifyError(err.message);
    } finally {
      setVerifying(false);
    }
  };

  const handleProvision = async () => {
    setProvisioning(true);
    setProvisionError(null);
    setProvisionStep(1);

    const stepInterval = setInterval(() => {
      setProvisionStep((prev) => (prev < 4 ? prev + 1 : prev));
    }, 3500);

    try {
      const res = await fetch('/api/onboarding/provision', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          primary_account: primaryAccount,
          primary_user: primaryUser,
          primary_password: primaryPassword,
          primary_role: primaryRole,
          secondary_account: secondaryAccount,
          secondary_user: secondaryUser,
          secondary_password: secondaryPassword,
          secondary_role: secondaryRole,
          database_name: databaseName || 'SF_DR_DEMO_DB',
          warehouse_name: warehouseName || 'DR_CONTROLLER_WH',
          failover_group_name: 'SF_DR_FAILOVER_GROUP',
          redirect_connection_name: 'SF_DR_GLOBAL_REDIRECT',
          primary_cloud_provider: primaryCloud,
          primary_cloud_region: primaryCloudRegion,
          primary_cloud_access_id: primaryCloudAccessId,
          primary_cloud_secret_key: primaryCloudSecretKey,
          secondary_cloud_provider: secondaryCloud,
          secondary_cloud_region: secondaryCloudRegion,
          secondary_cloud_access_id: secondaryCloudAccessId,
          secondary_cloud_secret_key: secondaryCloudSecretKey,
        }),
      });

      clearInterval(stepInterval);
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Provisioning failed');
      }

      setProvisionStep(5);
      setProvisionSuccess(true);
      setTimeout(() => {
        if (onSuccess) onSuccess(data);
      }, 2500);
    } catch (err) {
      clearInterval(stepInterval);
      setProvisionError(err.message);
    } finally {
      setProvisioning(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md overflow-y-auto animate-in fade-in duration-200">
      <div className="relative w-full max-w-4xl max-h-[90vh] flex flex-col bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden my-auto">
        {/* Header */}
        <div className="px-5 py-3 bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 border-b border-slate-800 flex items-center justify-between shrink-0">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-600/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400">
              <Shield className="w-4 h-4" />
            </div>
            <h2 className="text-base font-bold text-slate-100 flex items-center space-x-2">
              <span>Enterprise Multi-Cloud Onboarding</span>
              <span className="text-[10px] uppercase font-black tracking-wider bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 px-2 py-0.5 rounded-full">
                Zero-Touch SaaS
              </span>
            </h2>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={handleFillDemo}
              className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded border border-slate-700 font-semibold transition flex items-center space-x-1 cursor-pointer text-[11px]"
              title="Auto-fill verified cloud credentials"
            >
              <Zap className="w-3 h-3 text-amber-300" />
              <span>Fill Verified Credentials</span>
            </button>
            {onClose && (
              <button
                onClick={onClose}
                className="text-slate-400 hover:text-slate-200 p-1.5 rounded-lg hover:bg-slate-800 transition"
              >
                <X className="w-5 h-5" />
              </button>
            )}
          </div>
        </div>

        {/* Content Body */}
        <div className="p-5 space-y-5 overflow-y-auto flex-1">
          {provisionSuccess ? (
            <div className="py-10 text-center space-y-4 animate-in zoom-in-95 duration-300">
              <div className="w-16 h-16 bg-emerald-500/20 border border-emerald-500/40 text-emerald-400 rounded-full flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-10 h-10" />
              </div>
              <h3 className="text-2xl font-black text-white">🎉 READY TO MIGRATE & PROTECT!</h3>
              <p className="text-slate-300 text-sm max-w-lg mx-auto">
                Multi-Cloud Replication Link Established! Workloads cataloged, translated to standby cloud, and synchronized with <strong>RPO = 0</strong>.
              </p>
              <div className="flex justify-center pt-2">
                <Loader2 className="w-6 h-6 text-emerald-400 animate-spin" />
              </div>
            </div>
          ) : (
            <>
              {/* Account Input Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Primary Card */}
                <div className="p-5 bg-slate-950/40 border border-slate-800 rounded-xl space-y-3.5 relative overflow-hidden">
                  <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                    <div className="flex items-center space-x-2">
                      <Cloud className="w-4 h-4 text-emerald-400" />
                      <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
                        Primary Environment (Source)
                      </span>
                    </div>
                    <select
                      value={primaryCloud}
                      onChange={(e) => setPrimaryCloud(e.target.value)}
                      className="text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 px-2 py-0.5 rounded focus:outline-none cursor-pointer"
                    >
                      <option value="Auto-Detect" className="bg-slate-900 text-slate-200">Cloud: Auto-Detect</option>
                      <option value="AWS" className="bg-slate-900 text-slate-200">Cloud: AWS</option>
                      <option value="Azure" className="bg-slate-900 text-slate-200">Cloud: Azure</option>
                      <option value="GCP" className="bg-slate-900 text-slate-200">Cloud: GCP</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] font-medium text-slate-400 mb-1">
                      Snowflake Account Identifier (ORG-ACCOUNT)
                    </label>
                    <input
                      type="text"
                      value={primaryAccount}
                      onChange={(e) => setPrimaryAccount(e.target.value)}
                      placeholder="Enter Primary ORG-ACCOUNT"
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-[11px] font-medium text-slate-400 mb-1">Snowflake User</label>
                      <input
                        type="text"
                        value={primaryUser}
                        onChange={(e) => setPrimaryUser(e.target.value)}
                        placeholder="Admin Username"
                        className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-medium text-slate-400 mb-1">Snowflake Password</label>
                      <input
                        type="password"
                        value={primaryPassword}
                        onChange={(e) => setPrimaryPassword(e.target.value)}
                        placeholder="••••••••"
                        className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-[11px] font-medium text-slate-400 mb-1">
                      Protected Database Name
                    </label>
                    <input
                      type="text"
                      value={databaseName}
                      onChange={(e) => setDatabaseName(e.target.value)}
                      placeholder="Target Database to Replicate"
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  {/* Primary Cloud Provider API Credentials Section */}
                  <div className="pt-2.5 border-t border-slate-800/80 space-y-2.5">
                    <div className="flex items-center justify-between">
                      <span className="flex items-center space-x-1.5 text-[11px] font-bold uppercase tracking-wider text-amber-300">
                        <KeyRound className="w-3.5 h-3.5 shrink-0" />
                        <span>Primary Cloud API Auth</span>
                      </span>
                      <span className="text-[10px] text-slate-400 font-mono">Discovery & Stage</span>
                    </div>

                    <div className="grid grid-cols-3 gap-2">
                      <div className="col-span-2">
                        <label className="block text-[10px] text-slate-400 mb-1">Cloud Access Key / Client ID</label>
                        <input
                          type="text"
                          value={primaryCloudAccessId}
                          onChange={(e) => setPrimaryCloudAccessId(e.target.value)}
                          placeholder="Access Key ID / Client ID"
                          className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-amber-200 font-mono focus:outline-none focus:border-indigo-500"
                        />
                      </div>
                      <div className="col-span-1">
                        <label className="block text-[10px] text-slate-400 mb-1">Cloud Region</label>
                        <input
                          type="text"
                          value={primaryCloudRegion}
                          onChange={(e) => setPrimaryCloudRegion(e.target.value)}
                          placeholder="Auto / Region"
                          className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-amber-200 font-mono focus:outline-none focus:border-indigo-500"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-[10px] text-slate-400 mb-1">
                        Cloud Secret Key / Client Secret (API Password)
                      </label>
                      <input
                        type="password"
                        value={primaryCloudSecretKey}
                        onChange={(e) => setPrimaryCloudSecretKey(e.target.value)}
                        placeholder="Enter Cloud Secret Access Key / Service Token"
                        className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-amber-200 font-mono focus:outline-none focus:border-indigo-500"
                      />
                    </div>
                  </div>

                  {verifyResult?.primary && (
                    <div className="p-2.5 bg-emerald-950/40 border border-emerald-500/40 rounded-lg text-[11px] text-emerald-300 flex items-center justify-between">
                      <span className="flex items-center space-x-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                        <span>Verified: {verifyResult.primary.region}</span>
                      </span>
                      <span className="font-mono">{verifyResult.primary.ping_ms}ms</span>
                    </div>
                  )}
                </div>

                {/* Secondary Card */}
                <div className="p-5 bg-slate-950/40 border border-slate-800 rounded-xl space-y-3.5 relative overflow-hidden">
                  <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                    <div className="flex items-center space-x-2">
                      <Server className="w-4 h-4 text-sky-400" />
                      <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
                        Secondary Environment (Standby DR)
                      </span>
                    </div>
                    <select
                      value={secondaryCloud}
                      onChange={(e) => setSecondaryCloud(e.target.value)}
                      className="text-[10px] font-bold bg-sky-500/20 text-sky-300 border border-sky-500/30 px-2 py-0.5 rounded focus:outline-none cursor-pointer"
                    >
                      <option value="Auto-Detect" className="bg-slate-900 text-slate-200">Cloud: Auto-Detect</option>
                      <option value="Azure" className="bg-slate-900 text-slate-200">Cloud: Azure</option>
                      <option value="AWS" className="bg-slate-900 text-slate-200">Cloud: AWS</option>
                      <option value="GCP" className="bg-slate-900 text-slate-200">Cloud: GCP</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] font-medium text-slate-400 mb-1">
                      Snowflake Account Identifier (ORG-ACCOUNT)
                    </label>
                    <input
                      type="text"
                      value={secondaryAccount}
                      onChange={(e) => setSecondaryAccount(e.target.value)}
                      placeholder="Enter Secondary ORG-ACCOUNT"
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-[11px] font-medium text-slate-400 mb-1">Snowflake User</label>
                      <input
                        type="text"
                        value={secondaryUser}
                        onChange={(e) => setSecondaryUser(e.target.value)}
                        placeholder="Admin Username"
                        className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-medium text-slate-400 mb-1">Snowflake Password</label>
                      <input
                        type="password"
                        value={secondaryPassword}
                        onChange={(e) => setSecondaryPassword(e.target.value)}
                        placeholder="••••••••"
                        className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-[11px] font-medium text-slate-400 mb-1">
                      DR Controller Warehouse Name
                    </label>
                    <input
                      type="text"
                      value={warehouseName}
                      onChange={(e) => setWarehouseName(e.target.value)}
                      placeholder="Target Compute Warehouse"
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  {/* Secondary Cloud Provider API Credentials Section */}
                  <div className="pt-2.5 border-t border-slate-800/80 space-y-2.5">
                    <div className="flex items-center justify-between">
                      <span className="flex items-center space-x-1.5 text-[11px] font-bold uppercase tracking-wider text-sky-300">
                        <KeyRound className="w-3.5 h-3.5 shrink-0" />
                        <span>Standby Cloud API Auth</span>
                      </span>
                      <span className="text-[10px] text-slate-400 font-mono">Replica Hydration</span>
                    </div>

                    <div className="grid grid-cols-3 gap-2">
                      <div className="col-span-2">
                        <label className="block text-[10px] text-slate-400 mb-1">Subscription / Client / Access ID</label>
                        <input
                          type="text"
                          value={secondaryCloudAccessId}
                          onChange={(e) => setSecondaryCloudAccessId(e.target.value)}
                          placeholder="Subscription ID / Client ID"
                          className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-sky-200 font-mono focus:outline-none focus:border-indigo-500"
                        />
                      </div>
                      <div className="col-span-1">
                        <label className="block text-[10px] text-slate-400 mb-1">Cloud Region</label>
                        <input
                          type="text"
                          value={secondaryCloudRegion}
                          onChange={(e) => setSecondaryCloudRegion(e.target.value)}
                          placeholder="Auto / Region"
                          className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-sky-200 font-mono focus:outline-none focus:border-indigo-500"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-[10px] text-slate-400 mb-1">
                        Cloud Secret Key / Client Secret (API Password)
                      </label>
                      <input
                        type="password"
                        value={secondaryCloudSecretKey}
                        onChange={(e) => setSecondaryCloudSecretKey(e.target.value)}
                        placeholder="Enter Standby Cloud Secret / ARM Bearer Token"
                        className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-sky-200 font-mono focus:outline-none focus:border-indigo-500"
                      />
                    </div>
                  </div>

                  {verifyResult?.secondary && (
                    <div className="p-2.5 bg-sky-950/40 border border-sky-500/40 rounded-lg text-[11px] text-sky-300 flex items-center justify-between">
                      <span className="flex items-center space-x-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5 text-sky-400" />
                        <span>Verified: {verifyResult.secondary.region}</span>
                      </span>
                      <span className="font-mono">{verifyResult.secondary.ping_ms}ms</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Live Cloud Inventory Discovery Panel */}
              {verifyResult?.discovery && (
                <div className="p-3 bg-slate-950/90 border border-indigo-900/40 rounded-xl space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-200 flex items-center space-x-1.5">
                      <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
                      <span>Live Cloud Discovery Analysis (Zero-Mock Real Inventory)</span>
                    </span>
                    <span className="text-[10px] text-emerald-400 font-mono font-bold bg-emerald-950/60 border border-emerald-800/50 px-2 py-0.5 rounded">
                      Scanned in {verifyResult.discovery.duration_s || 0.4}s
                    </span>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[10px] font-mono">
                    <div className="p-2 bg-slate-900/90 rounded border border-slate-800">
                      <span className="text-slate-400 block">Primary EC2:</span>
                      <span className="text-slate-200 font-bold">
                        {verifyResult.discovery.aws?.instances?.length || 0} Running
                      </span>
                    </div>
                    <div className="p-2 bg-slate-900/90 rounded border border-slate-800">
                      <span className="text-slate-400 block">Primary S3:</span>
                      <span className="text-slate-200 font-bold">
                        {verifyResult.discovery.aws?.buckets?.length || 0} Buckets
                      </span>
                    </div>
                    <div className="p-2 bg-slate-900/90 rounded border border-slate-800">
                      <span className="text-slate-400 block">Primary Snowflake:</span>
                      <span className="text-slate-200 font-bold">
                        {verifyResult.discovery.snowflake_primary?.tables?.length || 0} Tables ({verifyResult.discovery.snowflake_primary?.total_rows || 0} Rows)
                      </span>
                    </div>
                    <div className="p-2 bg-slate-900/90 rounded border border-slate-800">
                      <span className="text-slate-400 block">Standby Snowflake:</span>
                      <span className="text-slate-200 font-bold">
                        {verifyResult.discovery.snowflake_secondary?.tables?.length || 0} Tables ({verifyResult.discovery.snowflake_secondary?.total_rows || 0} Rows)
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Status & Error Messages */}
              {verifyError && (
                <div className="p-3 bg-red-950/50 border border-red-500/50 rounded-xl text-xs text-red-300 flex items-center space-x-2">
                  <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
                  <span>Validation Error: {verifyError}</span>
                </div>
              )}

              {provisionError && (
                <div className="p-3 bg-red-950/50 border border-red-500/50 rounded-xl text-xs text-red-300 flex items-center space-x-2">
                  <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
                  <span>Provisioning Error: {provisionError}</span>
                </div>
              )}

              {/* Provisioning Progress Stepper */}
              {provisioning && (
                <div className="p-4 bg-slate-950 border border-indigo-900/60 rounded-xl space-y-2.5">
                  <div className="flex items-center justify-between text-xs font-bold text-slate-300">
                    <span className="flex items-center space-x-2">
                      <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />
                      <span>Zero-Touch Multi-Cloud DR Pipeline...</span>
                    </span>
                    <span>Step {provisionStep} of 5</span>
                  </div>
                  <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                    <div
                      className="bg-indigo-500 h-1.5 transition-all duration-500"
                      style={{ width: `${(provisionStep / 5) * 100}%` }}
                    ></div>
                  </div>
                  <p className="text-[11px] text-slate-400 font-mono">
                    {provisionStep === 1 && '1/5: Discovering Live Inventory & Provisioning Warehouses and Throw Stages...'}
                    {provisionStep === 2 && '2/5: Establishing Primary Failover Group & Global Anycast Redirect Connection...'}
                    {provisionStep === 3 && '3/5: Provisioning Secondary Catch Stages & Linking Failover Replica on Azure...'}
                    {provisionStep === 4 && '4/5: Performing WAN Delta Synchronization across AWS -> Azure...'}
                    {provisionStep === 5 && '5/5: Verifying RPO = 0 and Multi-Cloud Cryptographic Hash Parity...'}
                  </p>
                </div>
              )}

              {/* Action Buttons */}
              <div className="pt-2 flex items-center justify-end space-x-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={handleVerify}
                  disabled={verifying || provisioning}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-bold flex items-center space-x-1.5 transition disabled:opacity-50 cursor-pointer"
                >
                  {verifying ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Testing Connections...</span>
                    </>
                  ) : (
                    <>
                      <Zap className="w-3.5 h-3.5 text-amber-400" />
                      <span>🧪 Test & Auto-Detect Clouds</span>
                    </>
                  )}
                </button>

                <button
                  type="button"
                  onClick={handleProvision}
                  disabled={provisioning || verifying}
                  className="px-5 py-2 bg-gradient-to-r from-emerald-600 to-indigo-600 hover:from-emerald-500 hover:to-indigo-500 text-white rounded-lg text-xs font-black shadow-lg shadow-indigo-600/30 flex items-center space-x-2 transition disabled:opacity-50 cursor-pointer"
                >
                  {provisioning ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Provisioning Multi-Cloud DR...</span>
                    </>
                  ) : (
                    <>
                      <span>🚀 1-Click Bootstrap & Protect Platform</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </>
                  )}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
