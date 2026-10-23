/* Small, stateless DSP loops. No CRT, allocation, OS APIs, or AVX required.
 * Build with MSVC x64 /O2 /fp:strict /GS- /Zl and /NODEFAULTLIB.
 * Double intermediates and explicit float stores match Python array('f').
 */
#ifndef _WIN64
#error Build this library for Windows x64.
#endif

typedef unsigned __int64 count_t;
#define API __declspec(dllexport)

/* MSVC marks translation units containing floating point with this symbol. */
int _fltused = 0;

int __stdcall DllMain(void *module, unsigned long reason, void *reserved) {
    (void)module; (void)reason; (void)reserved;
    return 1;
}

API int nc_dsp_version(void) { return 1; }

API void nc_scale(float *data, count_t n, double factor) {
    count_t i;
    for (i = 0; i < n; ++i)
        data[i] = (float)((double)data[i] * factor);
}

API void nc_gain_clip(float *data, count_t n, double gain) {
    count_t i;
    for (i = 0; i < n; ++i) {
        /* The original gain loop stores float32 before its clipping loop. */
        float v = gain == 1.0 ? data[i] : (float)((double)data[i] * gain);
        data[i] = v > 1.0f ? 1.0f : (v < -1.0f ? -1.0f : v);
    }
}

API void nc_scale_clip(float *data, count_t n, double factor) {
    count_t i;
    for (i = 0; i < n; ++i) {
        double v = (double)data[i] * factor;
        data[i] = (float)(v > 1.0 ? 1.0 : (v < -1.0 ? -1.0 : v));
    }
}

API int nc_to_pcm16(const float *src, short *dst, count_t n, double scale) {
    count_t i;
    for (i = 0; i < n; ++i) {
        double v = (double)src[i] * scale;
        if (v != v) return 0;  /* Python int(NaN) raises ValueError. */
        if (v > 32767.0) v = 32767.0;
        else if (v < -32768.0) v = -32768.0;
        dst[i] = (short)(int)v;  /* truncation towards zero */
    }
    return 1;
}

API void nc_from_pcm16(const short *src, float *dst, count_t n, double scale) {
    count_t i;
    for (i = 0; i < n; ++i)
        dst[i] = (float)((double)src[i] * scale);
}

API double nc_sum_squares(const float *src, count_t n) {
    count_t i;
    double acc = 0.0;
    for (i = 0; i < n; ++i) {
        double v = (double)src[i];
        acc += v * v;
    }
    return acc;
}

API double nc_peak(const float *src, count_t n) {
    count_t i;
    double peak = 0.0;
    for (i = 0; i < n; ++i) {
        double v = (double)src[i];
        double a = v < 0.0 ? -v : v;
        if (a > peak) peak = a;
    }
    return peak;
}

API int nc_resample(const float *src, count_t src_n, float *dst, count_t dst_n,
                    double pos, double step) {
    count_t k;
    for (k = 0; k < dst_n; ++k) {
        double idx = pos + (double)k * step;
        count_t i0, i1;
        double frac;
        if (!(idx >= 0.0) || idx >= (double)src_n) return 0;
        i0 = (count_t)idx;
        frac = idx - (double)i0;
        i1 = i0 + 1 < src_n ? i0 + 1 : i0;
        dst[k] = (float)((double)src[i0] * (1.0 - frac)
                        + (double)src[i1] * frac);
    }
    return 1;
}
