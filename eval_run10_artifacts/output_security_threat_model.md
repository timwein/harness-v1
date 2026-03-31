# STRIDE Threat Model: Mobile Banking App

## Executive Summary

This threat model addresses a mobile banking application featuring biometric authentication, P2P payments, and third-party integrations. 
Most online payments in the EEA will require strong customer authentication. This means two-factor authentication which meets the European Banking Authority (EBA) requirements.
 
PSD2 SCA also requires dynamic linking, or tying the authentication tokens to the specific payment amount and payee.
 Critical threats include biometric spoofing attacks against devices lacking hardware security, API manipulation in third-party integrations, and man-in-the-middle attacks during P2P transfers. Priority mitigations focus on 
hardware-backed biometric binding to iOS Secure Enclave or Android TEE/StrongBox
, 
EMV tokenization implementation
, and step-up authentication for high-value transactions.

## Threat Matrix

| ID | STRIDE | Component | Threat Description | Likelihood | Impact | Risk Rating | Likelihood Justification | Impact Justification | Mitigations |
|---|---|---|---|---|---|---|---|---|---|
| **T-01** | Spoofing | Biometric Auth | 
Presentation attack using 3D-printed fingerprint or photo replay against face recognition on devices without dedicated secure enclave - item becomes permanently inaccessible but not deleted
 | Medium | Critical | High | Requires physical device access but 3D printing technology is accessible; successful bypass achievable with moderate technical skill | Complete account compromise enabling unauthorized transactions with potential regulatory violations under PSD2 | M-01, M-02, M-03 |
| **T-02** | Spoofing | P2P Payments | Account takeover via SIM swap enabling SMS OTP bypass for transaction authentication | Low | Critical | High | Requires social engineering attack on carrier and specific timing; success dependent on carrier security practices | Full account access enabling fraudulent P2P transfers with potential liability under PSD2 Strong Customer Authentication requirements | M-04, M-05 |
| **T-03** | Tampering | Third-party API | 
API response manipulation breaking PSD2 dynamic linking - attacker changes €500 payment to €5,000 or switches recipient account
 | Medium | High | High | Man-in-the-middle attacks achievable with network access; API manipulation requires moderate technical expertise | Significant financial loss and PSD2 dynamic linking compliance violation resulting in regulatory penalties | M-06, M-07 |
| **T-04** | Tampering | Biometric Auth | 
Biometric template invalidation bypass by exploiting userPresence vs biometryCurrentSet flags in iOS Keychain
 | Low | High | Medium | Requires deep iOS platform knowledge and specific exploit development; limited attack surface | Biometric authentication bypass enabling unauthorized access to high-value banking functions | M-08, M-09 |
| **T-05** | Repudiation | P2P Payments | Transaction denial by exploiting weak transaction logging in third-party payment rails | Medium | Medium | Medium | Achievable by manipulating transaction metadata during processing; requires understanding of payment rail architecture | Dispute resolution complications and potential financial liability in contested transactions | M-10, M-11 |
| **T-06** | Information Disclosure | Third-party API | 
Excessive data exposure in EMV tokenization revealing PAR data and transaction patterns to unauthorized third parties
 | Medium | Medium | Medium | API data leakage possible through misconfigured endpoints; requires API access and data analysis skills | Payment pattern disclosure and potential PCI DSS compliance violations but no direct financial loss | M-12, M-13 |
| **T-07** | Information Disclosure | Biometric Auth | 
Biometric template extraction from insecure storage when not protected by TEE encryption with device-specific key
 | Low | High | Medium | Requires device compromise and file system access; extraction tools are specialized but available | Permanent biometric compromise across multiple services; templates cannot be revoked like passwords | M-01, M-14 |
| **T-08** | Denial of Service | P2P Payments | 
Transaction flooding attacks overwhelming PSD2 SCA validation systems during peak usage periods
 | High | Medium | Medium | DDoS attacks readily achievable with common tools; SCA validation systems may lack robust rate limiting | Service disruption during peak periods affecting customer satisfaction but limited financial impact | M-15, M-16 |
| **T-09** | Denial of Service | Biometric Auth | 
Biometric lockout exploitation forcing KeyPermanentlyInvalidatedException and requiring full re-enrollment
 | Medium | Medium | Medium | Triggered by repeated failed biometric attempts; achievable with physical device access | Customer lockout requiring manual intervention and service degradation but no data compromise | M-17, M-18 |
| **T-10** | Elevation of Privilege | Third-party API | OAuth token privilege escalation through scope manipulation in third-party financial data integrations | Medium | High | High | OAuth vulnerabilities are well-documented; scope manipulation requires API knowledge but standard attack vectors exist | Access to financial data beyond authorized scope with potential PSD2 Open Banking compliance violations | M-19, M-20 |
| **T-11** | Spoofing | P2P Payments | 
Deep fake voice attacks against call center step-up authentication using AI-generated voice samples
 | Low | High | Medium | Requires voice sample collection and AI processing; technology becoming more accessible but still specialized | High-value transaction approval bypass through call center compromise | M-21, M-22 |
| **T-12** | Tampering | Biometric Auth | 
Device TEE compromise allowing extraction of private keys from Android KeyStore or iOS Keychain through physical attacks
 | Very Low | Critical | Medium | Requires physical device access and sophisticated hardware attacks; expensive and specialized equipment needed | Complete cryptographic compromise affecting all device-bound security controls | M-01, M-23 |
| **T-13** | Repudiation | Third-party API | 
Transaction attribution confusion in multi-token environments where PAR linking fails during EMV tokenization
 | Low | Medium | Low | Requires specific EMV tokenization implementation flaws; occurs in complex multi-merchant environments | Transaction attribution disputes but limited financial impact due to audit trail redundancy | M-24, M-25 |
| **T-14** | Information Disclosure | P2P Payments | 
PAN exposure during EMV transaction processing when tokenization is not properly implemented at merchant level
 | Medium | High | High | Common implementation error in EMV tokenization; occurs due to configuration mistakes rather than sophisticated attacks | Direct PAN exposure violating PCI DSS requirements with significant compliance and financial penalties | M-26, M-27 |
| **T-15** | Elevation of Privilege | Biometric Auth | Privilege escalation via biometric bypass on jailbroken/rooted devices with compromised platform security | Medium | High | High | Jailbreaking/rooting tools are widely available; platform security bypass achievable with moderate technical skill | Complete bypass of device-level security controls enabling unauthorized access to banking functions | M-28, M-29 |
| **T-16** | Denial of Service | Third-party API | API rate limiting exploitation causing transaction processing delays during high-volume P2P periods | High | Low | Medium | Standard API testing techniques can identify rate limiting weaknesses; easily automated attacks | Service delays affecting user experience but minimal financial impact or data exposure | M-30, M-31 |
| **T-17** | Spoofing | Third-party API | Man-in-the-middle attacks against third-party financial APIs lacking proper certificate pinning | Medium | High | High | Network-based attacks achievable with WiFi access or compromised network infrastructure | Financial API compromise enabling transaction manipulation and data theft | M-32, M-33 |
| **T-18** | Tampering | P2P Payments | 
EMV cryptogram manipulation allowing transaction amount modification without detection
 | Very Low | Critical | Medium | Requires deep EMV protocol knowledge and cryptographic attack capabilities; highly specialized and expensive | Complete transaction integrity compromise enabling undetected fraudulent modifications | M-34, M-35 |

## Risk Rating Framework

**Likelihood Scale:**
- Very Low (1): Requires specialized equipment/insider access
- Low (2): Requires technical skill and specific conditions  
- Medium (3): Achievable with moderate effort and tools
- High (4): Common attack vectors with readily available tools

**Impact Scale:**
- Low (1): Limited data exposure, minor financial loss
- Medium (2): Moderate data breach, significant financial impact
- High (3): Major data compromise, substantial financial loss
- Critical (4): Complete system compromise, regulatory violations

**Risk Calculation:** Risk = Likelihood × Impact
- Low: 1-4 | Medium: 5-8 | High: 9-12 | Critical: 13-16

## Prioritized Mitigations

### Phase 1 - Critical Security Controls (0-3 months)

**M-01** | **Hardware-Backed Biometric Authentication**
- 
Implement biometric binding to iOS Secure Enclave with encrypted memory and hardware-rooted key generation

- 
Configure Android StrongBox TEE with BiometricPrompt API enforcing user consent

- 
Set SecAccessControlCreateFlags to biometryCurrentSet for automatic invalidation on enrollment changes

- Addresses: T-01, T-07, T-12

**M-02** | **Liveness Detection Implementation**  
- Deploy 3D face mapping with depth analysis for Face ID authentication
- 
Implement passive liveness detection under 300ms response time

- Add presentation attack detection for fingerprint sensors using capacitive/thermal analysis
- Addresses: T-01

**M-03** | **Step-up Authentication for High-Value Transactions**
- 
Implement second factor authentication (SMS OTP/TOTP) for transactions exceeding €30 per PSD2 requirements

- Configure transaction amount thresholds: €100 (SMS), €500 (hardware token), €1000+ (call center)
- Add velocity-based step-up for multiple transactions within 1-hour periods
- Addresses: T-01, T-02

**M-26** | **EMV Tokenization Implementation**
- 
Deploy EMV Payment Tokenization with domain-specific tokens restricted to specific merchants and channels

- 
Implement Payment Account Reference (PAR) as 29-character alphanumeric identifier with BIN Controller assignment

- 
Configure tokenization meeting EMVCo specification for PCI DSS compliance relief eligibility

- Addresses: T-14

**M-32** | **Certificate Pinning and API Security**
- Implement certificate pinning for all third-party API connections
- Add API request signing using device-bound private keys stored in TEE
- Deploy API gateway with request/response validation and threat detection
- Addresses: T-17

### Phase 2 - Enhanced Controls (3-6 months)

**M-04** | **Anti-SIM Swap Protection**
- Deploy SIM binding verification using carrier APIs before SMS OTP delivery
- Implement device fingerprinting for SIM change detection
- Add call center verification for SIM swap requests within 24-hour authentication window
- Addresses: T-02

**M-06** | **PSD2 Dynamic Linking Enforcement**
- 
Implement cryptographic binding of transaction amount and recipient account with dynamic linking validation

- Deploy transaction signing using device-bound keys with amount/recipient verification
- Add real-time transaction monitoring for amount/recipient modifications
- Addresses: T-03

**M-19** | **OAuth Scope Validation**
- Implement strict OAuth scope validation with principle of least privilege
- Deploy token introspection for real-time permission verification
- Add scope elevation detection with automatic session termination
- Addresses: T-10

**M-28** | **Platform Security Validation**
- 
Implement device verification and validation for Android fragmentation addressing TEE implementation inconsistencies

- Deploy jailbreak/root detection with app termination on compromised devices
- Add hardware attestation verification for critical operations
- Addresses: T-15

### Phase 3 - Advanced Controls (6-12 months)

**M-15** | **Rate Limiting and DDoS Protection**
- Deploy adaptive rate limiting based on transaction patterns and user behavior
- Implement CAPTCHA challenges for suspicious transaction patterns
- Add circuit breaker patterns for third-party API protection
- Addresses: T-08, T-16

**M-21** | **Advanced Voice Authentication**
- Deploy voice biometrics with liveness detection for call center authentication
- Implement deepfake detection using voice pattern analysis
- Add multi-modal verification combining voice with knowledge factors
- Addresses: T-11

**M-24** | **Enhanced Transaction Logging**
- 
Deploy comprehensive PAR-based transaction tracking ensuring no reverse engineering to PAN identification

- Implement immutable transaction logs using blockchain-based verification
- Add cross-reference validation between tokens, PAR, and transaction records
- Addresses: T-13

## Regulatory Compliance Mapping

### PSD2 Strong Customer Authentication
- 
M-01, M-02, M-03 address SCA requirements for EU payment service providers with multi-factor authentication

- 
M-06 ensures dynamic linking compliance for transactions exceeding €30 exemption threshold


### PCI DSS Requirements  
- 
M-26 provides tokenization for PCI DSS scope reduction and cardholder data protection

- M-32 addresses PCI DSS Requirement 4 for encrypted data transmission

### Platform-Specific Security Standards
- 
M-01 leverages iOS Keychain Services and Android Keystore System for cryptographic framework protection

- 
M-28 ensures compliance with Android CDD Class 3 (Strong) biometric authentication requirements