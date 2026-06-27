"""
CSAM detection hook — INTEGRATION POINT, NOT A WORKING DETECTOR.

This module exists so that every image upload passes through a single,
mandatory checkpoint before being persisted. Right now that checkpoint does
not actually detect anything — there is no hash-matching against a known-CSAM
database, no ML classifier, nothing. It always returns NOT_IMPLEMENTED. This
file is the wiring; it is not the safety feature itself.

HOW THE PIPELINE WORKS (end to end)
─────────────────────────────────────────────────────────────────────────────
1. An image is uploaded (thread, post, or avatar).
2. core/image_utils.process_image() / process_avatar() cleans it:
   EXIF stripped, resized, re-encoded as WebP.
3. core/image_utils.compute_pdq_hash() generates a perceptual hash (pHash)
   of the cleaned bytes and stores it on the model (image_pdq_hash /
   avatar_pdq_hash). PDQ is Meta's open-source 256-bit perceptual hashing
   algorithm — the modern standard for CSAM hash-matching.
4. scan_image() (this module) is called with the same cleaned bytes.
   When a real provider is wired in, it compares the pHash against
   a database of known-CSAM hashes. Currently it does nothing.
5. If scan_image() returns FLAGGED: report_match() fires and the upload
   is rejected. Currently unreachable — scan_image() never returns FLAGGED.
6. If scan_image() returns CLEAN or NOT_IMPLEMENTED: the image is saved.

The stored pHash (step 3) is independent of the scan (step 4). It means
that once a real provider is wired in, historical images can be retroactively
checked by querying stored hashes against the provider's database — without
re-downloading or re-processing every image.

WHY THIS ISN'T JUST IMPLEMENTED OUTRIGHT
─────────────────────────────────────────────────────────────────────────────
Real CSAM hash-matching works against hash databases maintained by NCMEC,
the IWF, or commercial equivalents (Microsoft PhotoDNA, Thorn Safer, Google
CSAI Match). Access to those databases requires a vetted agreement with the
issuing organisation — it is not a library you can pip install, and this
codebase ships with no such agreement.

The pHashing in step 3 IS open source and requires no agreement — you
can generate pHashes freely. What you cannot do without provider access
is have anything to compare them against. The comparison step is what lives
here in scan_image().

Anyone claiming to ship "CSAM detection" without a provider agreement would
be shipping a placebo. This module is deliberately honest about being a
placeholder so that no operator mistakes "the hook exists" for "the
protection exists".

WHAT AN OPERATOR MUST DO BEFORE THIS IS REAL PROTECTION
─────────────────────────────────────────────────────────────────────────────
1. Obtain access to a hash-matching provider appropriate to your
   jurisdiction. Starting points:
   - UK: Internet Watch Foundation (IWF) — Hash List service
     https://www.iwf.org.uk/our-technology/our-products-and-services/
   - US: NCMEC hash-sharing programme (via CyberTipline reporting
     relationship) — https://www.missingkids.org/gethelpnow/cybertipline
   - Commercial (no direct NCMEC/IWF relationship required):
     Microsoft PhotoDNA, Thorn Safer, Google CSAI Match
   All require a formal application. This is not optional.

2. Implement scan_image() below to call your chosen provider with
   `image_bytes` (already a clean WebP stream at this point), map its
   response onto ScanVerdict.CLEAN or ScanVerdict.FLAGGED, and return a
   ScanResult. The stored pHash (on Thread.image_pdq_hash etc.) can
   be passed directly to providers that accept pHashes via API — you
   do not need to recompute it.

3. Implement the reporting leg in report_match(): on a positive match,
   your obligation is to report to your national authority — NCMEC's
   CyberTipline in the US, the NCA's CSEA reporting portal in the UK —
   not just to log it locally. This is a legal floor, not a best effort.

4. Do NOT remove the call sites in core/views.py. They are the permanent
   floor described in COMPLIANCE.md — there is intentionally no
   SiteSettings toggle for this checkpoint.

5. Consider retroactive scanning: the stored pHashes on Thread,
   Post, and User mean you can query your provider against existing
   content without reprocessing images. Build a management command to
   do this once your provider integration is live.

6. Get legal advice before going live. Reporting obligations, retention
   rules for matched content, and what you may and may not do with a
   positive match vary by jurisdiction and carry real legal weight.

See COMPLIANCE.md for the operator-responsibility framing this sits inside.
"""
import logging

logger = logging.getLogger('facechan.csam')


class ScanVerdict:
    """
    Explicit three-state result. The point of having NOT_IMPLEMENTED as a
    distinct state — rather than just returning CLEAN when there's no
    detector wired up — is so nothing in this codebase can ever claim or
    imply "scanned, found nothing" when what actually happened is "did not
    scan". Logs, admin views, and any future status reporting should treat
    NOT_IMPLEMENTED as "unknown / unprotected", never as "safe".
    """
    CLEAN = 'clean'
    FLAGGED = 'flagged'
    NOT_IMPLEMENTED = 'not_implemented'


class ScanResult:
    def __init__(self, verdict, detail=''):
        self.verdict = verdict
        self.detail = detail

    @property
    def is_flagged(self):
        return self.verdict == ScanVerdict.FLAGGED

    def __repr__(self):
        return f'<ScanResult {self.verdict}: {self.detail}>'


def scan_image(image_bytes):
    """
    THE INTEGRATION POINT. Called once per image upload, after processing
    (resize/EXIF-strip/WebP conversion) and before the file is persisted.

    Currently always returns NOT_IMPLEMENTED — see module docstring.

    To wire up a real provider: call it here with `image_bytes` (a clean
    WebP byte stream). If your provider accepts pHashes directly, you
    can compute or retrieve the stored hash rather than passing raw bytes —
    see compute_pdq_hash() in core/image_utils.py.

    Map the provider response onto ScanVerdict.CLEAN or ScanVerdict.FLAGGED
    and return a ScanResult. Keep this synchronous if possible — it sits in
    the upload request path. If a provider is only async, flip to a queued
    post-upload scan, but note that creates a window where unscanned content
    is briefly live.
    """
    logger.warning(
        'csam_detection.scan_image() called but no provider is configured — '
        'this upload was NOT scanned. See core/csam_detection.py.'
    )
    return ScanResult(
        ScanVerdict.NOT_IMPLEMENTED,
        detail='No detection provider configured.'
    )


def report_match(scan_result, *, context):
    """
    Called when scan_image() returns FLAGGED. Currently unreachable in
    practice since scan_image() never returns FLAGGED — but the call site
    exists in core/views.py so the reporting leg has a home once detection
    is real.

    `context` is a dict describing the upload — uploader id, content type
    (thread/post/avatar), thread/post id where relevant. Keep it minimal;
    be deliberate about what you log since this data may need careful
    handling under your jurisdiction's evidence-preservation rules.

    A real implementation must, at minimum:
    - Prevent the content from being served (it must not go live, or must
      be pulled immediately if a race let it through)
    - Preserve evidence per your national authority's retention requirements
      — do not casually delete matched content; get legal advice on this
    - Submit a mandatory report to your national authority:
        UK: NCA CEOP / IWF reporting portal
        US: NCMEC CyberTipline — https://www.missingkids.org/gethelpnow/cybertipline
    - Notify the instance operator (SiteSettings.moderation_contact) out-of-band
    """
    logger.critical(
        'report_match() invoked but has no implementation. A flagged '
        'image was NOT reported anywhere. context=%r', context
    )
    raise NotImplementedError(
        'CSAM match reporting is not implemented. See core/csam_detection.py '
        'for what an operator must build before this can fire for real.'
    )
