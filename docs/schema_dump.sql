--
-- PostgreSQL database dump
--

\restrict r6iotLfmYdeiOFAxNbIQQoAVDKyFP8gGRTT7xchf2UkvLFlaNUrnGzhTWoK3fOV

-- Dumped from database version 18.6 (Ubuntu 18.6-0ubuntu0.26.04.1)
-- Dumped by pg_dump version 18.6 (Ubuntu 18.6-0ubuntu0.26.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: prevent_audit_tampering(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.prevent_audit_tampering() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
                            BEGIN
                                RAISE EXCEPTION 'Audit trail is append-only. UPDATE and DELETE operations are strictly prohibited on auction_events.';
                            END;
                            $$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: auction_configs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auction_configs (
    id character varying(36) NOT NULL,
    rfq_id character varying(36) NOT NULL,
    trigger_window_minutes integer NOT NULL,
    extension_minutes integer NOT NULL,
    trigger_type character varying(30) NOT NULL,
    bid_visibility character varying(20) NOT NULL,
    min_decrement numeric(12,2),
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    CONSTRAINT chk_extension_minutes_pos CHECK ((extension_minutes > 0)),
    CONSTRAINT chk_trigger_window_pos CHECK ((trigger_window_minutes > 0))
);


--
-- Name: auction_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auction_events (
    id character varying(36) NOT NULL,
    rfq_id character varying(36) NOT NULL,
    bid_id character varying(36),
    event_type character varying(50) NOT NULL,
    payload json NOT NULL,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: auction_extensions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auction_extensions (
    id character varying(36) NOT NULL,
    rfq_id character varying(36) NOT NULL,
    triggering_bid_id character varying(36) NOT NULL,
    previous_close timestamp with time zone NOT NULL,
    new_close timestamp with time zone NOT NULL,
    trigger_type character varying(30) NOT NULL,
    reason text NOT NULL,
    is_clamped boolean NOT NULL,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: bids; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bids (
    id character varying(36) NOT NULL,
    rfq_id character varying(36) NOT NULL,
    supplier_id character varying(36) NOT NULL,
    submitted_by character varying(36) NOT NULL,
    freight_charges numeric(12,2) NOT NULL,
    origin_charges numeric(12,2) NOT NULL,
    destination_charges numeric(12,2) NOT NULL,
    total numeric(12,2) NOT NULL,
    transit_time_days integer NOT NULL,
    quote_validity_date timestamp with time zone NOT NULL,
    carrier_name character varying(255) NOT NULL,
    idempotency_key character varying(128),
    created_at timestamp with time zone NOT NULL,
    CONSTRAINT chk_destination_non_neg CHECK ((destination_charges >= (0)::numeric)),
    CONSTRAINT chk_freight_pos CHECK ((freight_charges > (0)::numeric)),
    CONSTRAINT chk_origin_non_neg CHECK ((origin_charges >= (0)::numeric)),
    CONSTRAINT chk_total_equals_components CHECK ((total = ((freight_charges + origin_charges) + destination_charges))),
    CONSTRAINT chk_total_pos CHECK ((total > (0)::numeric)),
    CONSTRAINT chk_transit_pos CHECK ((transit_time_days > 0))
);


--
-- Name: rfq_invitations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rfq_invitations (
    id character varying(36) NOT NULL,
    rfq_id character varying(36) NOT NULL,
    supplier_id character varying(36) NOT NULL,
    status character varying(20) NOT NULL,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: rfqs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rfqs (
    id character varying(36) NOT NULL,
    reference_id character varying(64) NOT NULL,
    title character varying(255) NOT NULL,
    description text,
    origin character varying(255) NOT NULL,
    destination character varying(255) NOT NULL,
    pickup_date timestamp with time zone NOT NULL,
    bid_start timestamp with time zone NOT NULL,
    bid_close timestamp with time zone NOT NULL,
    effective_close timestamp with time zone NOT NULL,
    forced_close timestamp with time zone NOT NULL,
    status character varying(20) NOT NULL,
    created_by character varying(36) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    CONSTRAINT chk_bid_close_gt_bid_start CHECK ((bid_close > bid_start)),
    CONSTRAINT chk_forced_close_gt_bid_close CHECK ((forced_close > bid_close)),
    CONSTRAINT chk_pickup_date_gt_bid_close CHECK ((pickup_date > bid_close))
);


--
-- Name: suppliers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.suppliers (
    id character varying(36) NOT NULL,
    name character varying(255) NOT NULL,
    code character varying(50) NOT NULL,
    contact_email character varying(255) NOT NULL,
    contact_phone character varying(50),
    is_active boolean NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id character varying(36) NOT NULL,
    email character varying(255) NOT NULL,
    password_hash character varying(255) NOT NULL,
    full_name character varying(255) NOT NULL,
    role character varying(20) NOT NULL,
    supplier_id character varying(36),
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: auction_configs auction_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auction_configs
    ADD CONSTRAINT auction_configs_pkey PRIMARY KEY (id);


--
-- Name: auction_configs auction_configs_rfq_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auction_configs
    ADD CONSTRAINT auction_configs_rfq_id_key UNIQUE (rfq_id);


--
-- Name: auction_events auction_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auction_events
    ADD CONSTRAINT auction_events_pkey PRIMARY KEY (id);


--
-- Name: auction_extensions auction_extensions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auction_extensions
    ADD CONSTRAINT auction_extensions_pkey PRIMARY KEY (id);


--
-- Name: bids bids_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bids
    ADD CONSTRAINT bids_pkey PRIMARY KEY (id);


--
-- Name: rfq_invitations rfq_invitations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rfq_invitations
    ADD CONSTRAINT rfq_invitations_pkey PRIMARY KEY (id);


--
-- Name: rfqs rfqs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rfqs
    ADD CONSTRAINT rfqs_pkey PRIMARY KEY (id);


--
-- Name: suppliers suppliers_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.suppliers
    ADD CONSTRAINT suppliers_name_key UNIQUE (name);


--
-- Name: suppliers suppliers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.suppliers
    ADD CONSTRAINT suppliers_pkey PRIMARY KEY (id);


--
-- Name: rfq_invitations uq_rfq_supplier_invitation; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rfq_invitations
    ADD CONSTRAINT uq_rfq_supplier_invitation UNIQUE (rfq_id, supplier_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: idx_auction_events_rfq_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_auction_events_rfq_created ON public.auction_events USING btree (rfq_id, created_at);


--
-- Name: idx_bids_rfq_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bids_rfq_created ON public.bids USING btree (rfq_id, created_at);


--
-- Name: idx_bids_rfq_supplier_idem; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_bids_rfq_supplier_idem ON public.bids USING btree (rfq_id, supplier_id, idempotency_key) WHERE (idempotency_key IS NOT NULL);


--
-- Name: idx_bids_rfq_total; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bids_rfq_total ON public.bids USING btree (rfq_id, total);


--
-- Name: idx_bids_supplier_rfq; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bids_supplier_rfq ON public.bids USING btree (supplier_id, rfq_id, created_at);


--
-- Name: idx_extensions_rfq; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_extensions_rfq ON public.auction_extensions USING btree (rfq_id, created_at);


--
-- Name: idx_invitations_rfq; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_invitations_rfq ON public.rfq_invitations USING btree (rfq_id);


--
-- Name: idx_invitations_supplier; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_invitations_supplier ON public.rfq_invitations USING btree (supplier_id);


--
-- Name: idx_rfqs_status_effective; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rfqs_status_effective ON public.rfqs USING btree (status, effective_close);


--
-- Name: ix_rfqs_reference_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_rfqs_reference_id ON public.rfqs USING btree (reference_id);


--
-- Name: ix_suppliers_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_suppliers_code ON public.suppliers USING btree (code);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: auction_events trg_prevent_audit_tampering; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_prevent_audit_tampering BEFORE DELETE OR UPDATE ON public.auction_events FOR EACH ROW EXECUTE FUNCTION public.prevent_audit_tampering();


--
-- Name: auction_configs auction_configs_rfq_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auction_configs
    ADD CONSTRAINT auction_configs_rfq_id_fkey FOREIGN KEY (rfq_id) REFERENCES public.rfqs(id) ON DELETE CASCADE;


--
-- Name: auction_events auction_events_bid_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auction_events
    ADD CONSTRAINT auction_events_bid_id_fkey FOREIGN KEY (bid_id) REFERENCES public.bids(id) ON DELETE RESTRICT;


--
-- Name: auction_events auction_events_rfq_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auction_events
    ADD CONSTRAINT auction_events_rfq_id_fkey FOREIGN KEY (rfq_id) REFERENCES public.rfqs(id) ON DELETE CASCADE;


--
-- Name: auction_extensions auction_extensions_rfq_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auction_extensions
    ADD CONSTRAINT auction_extensions_rfq_id_fkey FOREIGN KEY (rfq_id) REFERENCES public.rfqs(id) ON DELETE CASCADE;


--
-- Name: auction_extensions auction_extensions_triggering_bid_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auction_extensions
    ADD CONSTRAINT auction_extensions_triggering_bid_id_fkey FOREIGN KEY (triggering_bid_id) REFERENCES public.bids(id) ON DELETE RESTRICT;


--
-- Name: bids bids_rfq_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bids
    ADD CONSTRAINT bids_rfq_id_fkey FOREIGN KEY (rfq_id) REFERENCES public.rfqs(id) ON DELETE CASCADE;


--
-- Name: bids bids_submitted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bids
    ADD CONSTRAINT bids_submitted_by_fkey FOREIGN KEY (submitted_by) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: bids bids_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bids
    ADD CONSTRAINT bids_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id) ON DELETE CASCADE;


--
-- Name: rfq_invitations rfq_invitations_rfq_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rfq_invitations
    ADD CONSTRAINT rfq_invitations_rfq_id_fkey FOREIGN KEY (rfq_id) REFERENCES public.rfqs(id) ON DELETE CASCADE;


--
-- Name: rfq_invitations rfq_invitations_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rfq_invitations
    ADD CONSTRAINT rfq_invitations_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id) ON DELETE CASCADE;


--
-- Name: rfqs rfqs_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rfqs
    ADD CONSTRAINT rfqs_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: users users_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id) ON DELETE SET NULL;


--
-- PostgreSQL database dump complete
--

\unrestrict r6iotLfmYdeiOFAxNbIQQoAVDKyFP8gGRTT7xchf2UkvLFlaNUrnGzhTWoK3fOV

