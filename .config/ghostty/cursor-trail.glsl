// Ghostty supplies cursor rectangles in pixels, with the origin at their top left.
void mainImage(out vec4 color, in vec2 pixel) {
    color = texture(iChannel0, pixel / iResolution.xy);
    const float duration = 0.16;
    float age = iTime - iTimeCursorChange;
    if (iFocus == 0 || iCursorVisible == 0 || age < 0.0 || age >= duration ||
        min(iPreviousCursor.z, iPreviousCursor.w) <= 0.0) return;

    vec2 center = iCurrentCursor.xy + vec2(0.5, -0.5) * iCurrentCursor.zw;
    vec2 previous = iPreviousCursor.xy + vec2(0.5, -0.5) * iPreviousCursor.zw;
    vec2 motion = center - previous;
    float distanceMoved = length(motion);
    if (distanceMoved < 1.0) return;

    // Limit long jumps and retract the tail toward the current cursor.
    vec2 direction = motion / distanceMoved;
    float remaining = 1.0 - age / duration;
    float trailLength = min(distanceMoved, 5.0 * iCurrentCursor.w) * remaining;
    float behind = dot(center - pixel, direction);
    if (behind <= 0.0 || behind >= trailLength ||
        all(lessThanEqual(abs(pixel - center), 0.5 * iCurrentCursor.zw))) return;

    float taper = 1.0 - behind / trailLength;
    float radius = max(1.0, 0.20 * iCurrentCursor.w) * taper;
    float across = length(pixel - (center - behind * direction));
    float coverage = 1.0 - smoothstep(max(0.0, radius - 1.0), radius + 1.0, across);
    float opacity = 0.55 * remaining * taper * coverage * iCurrentCursorColor.a;
    color = vec4(iCurrentCursorColor.rgb, 1.0) * opacity + color * (1.0 - opacity);
}
