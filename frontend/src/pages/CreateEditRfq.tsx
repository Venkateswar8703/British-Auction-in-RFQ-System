import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api, ApiError } from '../services/api';
import { Supplier, TriggerType } from '../types';
import { ArrowLeft, Save, AlertCircle } from 'lucide-react';
import { addHours, addDays, format } from 'date-fns';

export const CreateEditRfq: React.FC = () => {
  const { rfqId } = useParams<{ rfqId: string }>();
  const navigate = useNavigate();
  const isEditing = Boolean(rfqId);

  const now = new Date();
  const [referenceId, setReferenceId] = useState<string>(
    `RFQ-2026-${Math.floor(100 + Math.random() * 900)}`
  );
  const [title, setTitle] = useState<string>('Transpacific 40ft HC Container Liner Contract');
  const [description, setDescription] = useState<string>('Standard 40ft dry van high-cube containers with guaranteed weekly allocation.');
  const [origin, setOrigin] = useState<string>('Shanghai Port (CNSHA)');
  const [destination, setDestination] = useState<string>('Port of Long Beach (USLGB)');
  const [pickupDate, setPickupDate] = useState<string>(format(addDays(now, 20), 'yyyy-MM-dd'));
  const [bidStart, setBidStart] = useState<string>(format(now, "yyyy-MM-dd'T'HH:mm"));
  const [bidClose, setBidClose] = useState<string>(format(addHours(now, 2), "yyyy-MM-dd'T'HH:mm"));
  const [forcedClose, setForcedClose] = useState<string>(format(addHours(now, 4), "yyyy-MM-dd'T'HH:mm"));

  const [triggerWindowMinutes, setTriggerWindowMinutes] = useState<number>(10);
  const [extensionMinutes, setExtensionMinutes] = useState<number>(5);
  const [triggerType, setTriggerType] = useState<TriggerType>('L1_CHANGE');

  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [invitedSupplierIds, setInvitedSupplierIds] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    async function init() {
      try {
        const suppList = await api.listSuppliers();
        setSuppliers(suppList);

        if (isEditing && rfqId) {
          const rfq = await api.getRfq(rfqId);
          if (rfq.status !== 'SCHEDULED') {
            setErrorMessage('Auction has already commenced or concluded and is locked against modifications.');
          }
          setReferenceId(rfq.reference_id);
          setTitle(rfq.title);
          setDescription(rfq.description || '');
          setOrigin(rfq.origin);
          setDestination(rfq.destination);
          setPickupDate(format(new Date(rfq.pickup_date), 'yyyy-MM-dd'));
          setBidStart(format(new Date(rfq.bid_start), "yyyy-MM-dd'T'HH:mm"));
          setBidClose(format(new Date(rfq.bid_close), "yyyy-MM-dd'T'HH:mm"));
          setForcedClose(format(new Date(rfq.forced_close), "yyyy-MM-dd'T'HH:mm"));

          if (rfq.config) {
            setTriggerWindowMinutes(rfq.config.trigger_window_minutes);
            setExtensionMinutes(rfq.config.extension_minutes);
            setTriggerType(rfq.config.trigger_type);
          }
          if (rfq.invitations) {
            setInvitedSupplierIds(rfq.invitations.map((i) => i.supplier_id));
          }
        } else {
          setInvitedSupplierIds(suppList.slice(0, 5).map((s) => s.id));
        }
      } catch (err: any) {
        setErrorMessage(err.message || 'Failed to initialize form.');
      } finally {
        setIsLoading(false);
      }
    }
    init();
  }, [isEditing, rfqId]);

  const toggleSupplier = (supplierId: string) => {
    if (invitedSupplierIds.includes(supplierId)) {
      setInvitedSupplierIds(invitedSupplierIds.filter((id) => id !== supplierId));
    } else {
      setInvitedSupplierIds([...invitedSupplierIds, supplierId]);
    }
  };

  const selectAllSuppliers = () => {
    setInvitedSupplierIds(suppliers.map((s) => s.id));
  };

  const clearSuppliers = () => {
    setInvitedSupplierIds([]);
  };

  const validateDates = (): string | null => {
    const start = new Date(bidStart).getTime();
    const close = new Date(bidClose).getTime();
    const forced = new Date(forcedClose).getTime();
    const pickup = new Date(pickupDate).getTime();

    if (close <= start) {
      return 'Rule Violation: Bid Close Date & Time must be strictly after Bid Start Date & Time.';
    }
    if (forced <= close) {
      return 'Rule Violation: Forced Bid Close Time must be strictly greater than Bid Close Time.';
    }
    if (pickup <= close) {
      return 'Rule Violation: Cargo Pickup Date must be strictly after the Bid Close Time.';
    }
    if (invitedSupplierIds.length === 0) {
      return 'Validation: You must invite at least 1 supplier organization.';
    }
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    const validationErr = validateDates();
    if (validationErr) {
      setErrorMessage(validationErr);
      return;
    }

    setIsSubmitting(true);
    const payload = {
      reference_id: referenceId.trim(),
      title: title.trim(),
      description: description.trim() || undefined,
      origin: origin.trim(),
      destination: destination.trim(),
      pickup_date: new Date(pickupDate).toISOString(),
      bid_start: new Date(bidStart).toISOString(),
      bid_close: new Date(bidClose).toISOString(),
      forced_close: new Date(forcedClose).toISOString(),
      trigger_window_minutes: Number(triggerWindowMinutes),
      extension_minutes: Number(extensionMinutes),
      trigger_type: triggerType,
      invited_supplier_ids: invitedSupplierIds,
    };

    try {
      if (isEditing && rfqId) {
        await api.updateRfq(rfqId, payload);
      } else {
        await api.createRfq(payload);
      }
      navigate('/auctions');
    } catch (err: any) {
      if (err instanceof ApiError) {
        setErrorMessage(`[${err.code}] ${err.message}`);
      } else {
        setErrorMessage(err.message || 'Error saving RFQ');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-10 pb-16 text-meridian-ink">
      
      {/* Breadcrumb Header */}
      <div className="flex items-center gap-3 pb-3 border-b border-meridian-line font-mono text-xs">
        <button
          onClick={() => navigate('/auctions')}
          className="flex items-center gap-1 text-meridian-muted hover:text-meridian-ink transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Auctions</span>
        </button>
        <span className="text-meridian-line">/</span>
        <span className="text-meridian-ink font-bold">
          {isEditing ? `Edit RFQ: ${referenceId}` : 'Create British Auction RFQ'}
        </span>
      </div>

      <div>
        <div className="font-mono text-[11px] tracking-[0.08em] uppercase text-meridian-muted mb-1">
          CONFIGURATOR
        </div>
        <h1 className="text-3xl md:text-4xl font-heading font-medium tracking-tight text-meridian-ink">
          {isEditing ? 'Configure Scheduled RFQ' : 'New British Auction RFQ'}
        </h1>
        <p className="text-sm text-meridian-muted mt-2 leading-relaxed">
          Configure dynamic British Auction parameters (Trigger window X, Extension duration Y, and Qualifying event criteria).
        </p>
      </div>

      {errorMessage && (
        <div className="p-4 bg-meridian-orange text-meridian-ink border border-meridian-ink font-mono text-xs flex items-start gap-3">
          <AlertCircle className="w-5 h-5 shrink-0 text-meridian-ink mt-0.5" />
          <div>
            <div className="font-bold uppercase tracking-wider text-xs">Validation Failure</div>
            <div className="mt-0.5 font-sans">{errorMessage}</div>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-12">
        
        {/* Section 1: Editorial Two-Column: Routing Corridor */}
        <div className="editorial-rule pt-6 grid grid-cols-1 md:grid-cols-12 gap-6">
          <div className="md:col-span-4">
            <span className="font-mono text-[11px] tracking-[0.08em] uppercase text-meridian-muted block mb-1">
              01 / IDENTITY & ROUTING
            </span>
            <h2 className="font-heading text-lg font-medium text-meridian-ink">
              Corridor Specifications
            </h2>
            <p className="text-xs text-meridian-muted mt-1 leading-relaxed">
              Define the freight corridor ports, reference identifier, and contractual description.
            </p>
          </div>

          <div className="md:col-span-8 bg-meridian-surface border border-meridian-line p-6 space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
              <div>
                <label className="text-[11px] font-mono uppercase tracking-[0.08em] text-meridian-muted block mb-1">
                  Reference ID *
                </label>
                <input
                  type="text"
                  value={referenceId}
                  onChange={(e) => setReferenceId(e.target.value)}
                  disabled={isEditing}
                  className="input-underlined w-full font-mono text-xs font-bold"
                  required
                />
              </div>

              <div className="sm:col-span-2">
                <label className="text-[11px] font-mono uppercase tracking-[0.08em] text-meridian-muted block mb-1">
                  RFQ Title *
                </label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="input-underlined w-full text-xs font-semibold"
                  required
                />
              </div>
            </div>

            <div>
              <label className="text-[11px] font-mono uppercase tracking-[0.08em] text-meridian-muted block mb-1">
                Shipment / Service Specifications
              </label>
              <textarea
                rows={2}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full bg-meridian-surface border border-meridian-line p-2 text-xs text-meridian-ink focus:border-meridian-ink outline-none"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
              <div>
                <label className="text-[11px] font-mono uppercase tracking-[0.08em] text-meridian-muted block mb-1">
                  Origin Port *
                </label>
                <input
                  type="text"
                  value={origin}
                  onChange={(e) => setOrigin(e.target.value)}
                  className="input-underlined w-full text-xs font-medium"
                  required
                />
              </div>

              <div>
                <label className="text-[11px] font-mono uppercase tracking-[0.08em] text-meridian-muted block mb-1">
                  Destination Port *
                </label>
                <input
                  type="text"
                  value={destination}
                  onChange={(e) => setDestination(e.target.value)}
                  className="input-underlined w-full text-xs font-medium"
                  required
                />
              </div>

              <div>
                <label className="text-[11px] font-mono uppercase tracking-[0.08em] text-meridian-muted block mb-1">
                  Pickup Date *
                </label>
                <input
                  type="date"
                  value={pickupDate}
                  onChange={(e) => setPickupDate(e.target.value)}
                  className="input-underlined w-full text-xs font-medium"
                  required
                />
              </div>
            </div>
          </div>
        </div>

        {/* Section 2: British Auction Timing & Boundaries */}
        <div className="editorial-rule pt-6 grid grid-cols-1 md:grid-cols-12 gap-6">
          <div className="md:col-span-4">
            <span className="font-mono text-[11px] tracking-[0.08em] uppercase text-meridian-muted block mb-1">
              02 / TIMELINE BOUNDARIES
            </span>
            <h2 className="font-heading text-lg font-medium text-meridian-ink">
              Auction Schedule
            </h2>
            <p className="text-xs text-meridian-muted mt-1 leading-relaxed">
              Enforce strict server-side chronology: Forced Close &gt; Bid Close &gt; Bid Start.
            </p>
          </div>

          <div className="md:col-span-8 bg-meridian-surface border border-meridian-line p-6 space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
              <div>
                <label className="text-[11px] font-mono uppercase tracking-[0.08em] text-meridian-muted block mb-1">
                  Bid Start (UTC) *
                </label>
                <input
                  type="datetime-local"
                  value={bidStart}
                  onChange={(e) => setBidStart(e.target.value)}
                  className="input-underlined w-full font-mono text-xs"
                  required
                />
              </div>

              <div>
                <label className="text-[11px] font-mono uppercase tracking-[0.08em] text-meridian-muted block mb-1">
                  Bid Close (Initial) *
                </label>
                <input
                  type="datetime-local"
                  value={bidClose}
                  onChange={(e) => setBidClose(e.target.value)}
                  className="input-underlined w-full font-mono text-xs font-bold"
                  required
                />
              </div>

              <div>
                <label className="text-[11px] font-mono uppercase tracking-[0.08em] text-meridian-orange font-bold block mb-1">
                  Forced Close (Cap) *
                </label>
                <input
                  type="datetime-local"
                  value={forcedClose}
                  onChange={(e) => setForcedClose(e.target.value)}
                  className="input-underlined w-full font-mono text-xs font-bold text-meridian-orange"
                  required
                />
              </div>
            </div>

            <p className="text-[11px] font-mono text-meridian-muted">
              • Strict British Rule: All dynamic soft-close extensions will automatically clamp at the Forced Close limit.
            </p>
          </div>
        </div>

        {/* Section 3: Extension Trigger Parameters (X & Y) */}
        <div className="editorial-rule pt-6 grid grid-cols-1 md:grid-cols-12 gap-6">
          <div className="md:col-span-4">
            <span className="font-mono text-[11px] tracking-[0.08em] uppercase text-meridian-muted block mb-1">
              03 / EXTENSION ENGINE
            </span>
            <h2 className="font-heading text-lg font-medium text-meridian-ink">
              Triggers (X & Y)
            </h2>
            <p className="text-xs text-meridian-muted mt-1 leading-relaxed">
              Activity inside window X triggers extension duration Y based on qualifying event type.
            </p>
          </div>

          <div className="md:col-span-8 bg-meridian-surface border border-meridian-line p-6 space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
              <div>
                <label className="text-[11px] font-mono uppercase tracking-[0.08em] text-meridian-muted block mb-1">
                  Window (X Minutes) *
                </label>
                <input
                  type="number"
                  min="1"
                  max="120"
                  value={triggerWindowMinutes}
                  onChange={(e) => setTriggerWindowMinutes(parseInt(e.target.value, 10))}
                  className="input-underlined w-full font-mono text-xs font-bold"
                  required
                />
                <span className="text-[10px] text-meridian-muted font-mono mt-1 block">
                  Last X minutes monitored
                </span>
              </div>

              <div>
                <label className="text-[11px] font-mono uppercase tracking-[0.08em] text-meridian-muted block mb-1">
                  Extension (Y Minutes) *
                </label>
                <input
                  type="number"
                  min="1"
                  max="60"
                  value={extensionMinutes}
                  onChange={(e) => setExtensionMinutes(parseInt(e.target.value, 10))}
                  className="input-underlined w-full font-mono text-xs font-bold"
                  required
                />
                <span className="text-[10px] text-meridian-muted font-mono mt-1 block">
                  Time added per extension
                </span>
              </div>

              <div>
                <label className="text-[11px] font-mono uppercase tracking-[0.08em] text-meridian-muted block mb-1">
                  Trigger Event Type *
                </label>
                <select
                  value={triggerType}
                  onChange={(e) => setTriggerType(e.target.value as TriggerType)}
                  className="w-full bg-meridian-surface border border-meridian-line p-2 text-xs font-mono font-bold text-meridian-ink focus:border-meridian-ink outline-none mt-1"
                >
                  <option value="L1_CHANGE">L1_CHANGE (Lowest Bidder Shifts)</option>
                  <option value="ANY_RANK_CHANGE">ANY_RANK_CHANGE (Any Rank Shifts)</option>
                  <option value="BID_RECEIVED">BID_RECEIVED (Any Bid In Window)</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* Section 4: Carrier Whitelist */}
        <div className="editorial-rule pt-6 grid grid-cols-1 md:grid-cols-12 gap-6">
          <div className="md:col-span-4">
            <span className="font-mono text-[11px] tracking-[0.08em] uppercase text-meridian-muted block mb-1">
              04 / INVITED CARRIERS
            </span>
            <h2 className="font-heading text-lg font-medium text-meridian-ink">
              Carrier Access
            </h2>
            <p className="text-xs text-meridian-muted mt-1 leading-relaxed">
              Only invited carriers are authorized by RBAC to view and place authoritative quotes.
            </p>
          </div>

          <div className="md:col-span-8 bg-meridian-surface border border-meridian-line p-6">
            <div className="flex items-center justify-between border-b border-meridian-line pb-2 mb-4 font-mono text-xs">
              <span className="text-meridian-muted uppercase text-[11px]">
                {invitedSupplierIds.length} Carriers Whitelisted
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={selectAllSuppliers}
                  className="text-meridian-ink font-semibold hover:underline"
                >
                  Select All
                </button>
                <span>•</span>
                <button
                  type="button"
                  onClick={clearSuppliers}
                  className="text-meridian-muted hover:text-meridian-ink"
                >
                  Clear
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {suppliers.map((s) => {
                const isSelected = invitedSupplierIds.includes(s.id);
                return (
                  <div
                    key={s.id}
                    onClick={() => toggleSupplier(s.id)}
                    className={`p-3 border cursor-pointer select-none transition-all flex items-center justify-between ${
                      isSelected
                        ? 'bg-meridian-surfaceDeep border-meridian-ink text-meridian-ink font-semibold'
                        : 'bg-meridian-surface border-meridian-line text-meridian-muted hover:border-meridian-ink'
                    }`}
                  >
                    <div>
                      <div className="text-xs text-meridian-ink font-medium">{s.name}</div>
                      <div className="text-[10px] text-meridian-muted font-mono">{s.code}</div>
                    </div>
                    <div className={`w-4 h-4 border flex items-center justify-center font-bold text-xs ${
                      isSelected ? 'bg-meridian-ink border-meridian-ink text-meridian-ivory' : 'border-meridian-line'
                    }`}>
                      {isSelected && '✓'}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Submit Action Strip */}
        <div className="pt-6 border-t border-meridian-line flex items-center justify-end gap-4 font-mono text-xs">
          <button
            type="button"
            onClick={() => navigate('/auctions')}
            className="btn-secondary px-5 py-2.5 uppercase"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            className="btn-primary px-6 py-2.5 uppercase font-bold flex items-center gap-2"
          >
            <Save className="w-4 h-4" />
            {isSubmitting ? 'Saving Auction...' : isEditing ? 'Update RFQ' : 'Launch British Auction'}
          </button>
        </div>

      </form>
    </div>
  );
};
