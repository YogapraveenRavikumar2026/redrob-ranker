/* ============================================
   RECRUITER BRAIN — Three.js + Animations
   Neural network particle background + scroll FX
   ============================================ */

// ============ THREE.JS NEURAL NETWORK BACKGROUND ============
(function initThreeJS() {
    const canvas = document.getElementById('bg-canvas');
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    // Particles
    const particleCount = 180;
    const positions = new Float32Array(particleCount * 3);
    const velocities = [];
    const spread = 30;

    for (let i = 0; i < particleCount; i++) {
        positions[i * 3]     = (Math.random() - 0.5) * spread;
        positions[i * 3 + 1] = (Math.random() - 0.5) * spread;
        positions[i * 3 + 2] = (Math.random() - 0.5) * spread;
        velocities.push({
            x: (Math.random() - 0.5) * 0.008,
            y: (Math.random() - 0.5) * 0.008,
            z: (Math.random() - 0.5) * 0.008
        });
    }

    // Points (nodes)
    const pointsGeometry = new THREE.BufferGeometry();
    pointsGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

    const pointsMaterial = new THREE.PointsMaterial({
        color: 0xF58529,
        size: 0.08,
        transparent: true,
        opacity: 0.8,
        sizeAttenuation: true
    });

    const points = new THREE.Points(pointsGeometry, pointsMaterial);
    scene.add(points);

    // Lines (connections)
    const linesMaterial = new THREE.LineBasicMaterial({
        color: 0xE84393,
        transparent: true,
        opacity: 0.08
    });

    let linesGroup = new THREE.Group();
    scene.add(linesGroup);

    camera.position.z = 15;

    // Mouse interaction
    let mouseX = 0, mouseY = 0;
    document.addEventListener('mousemove', (e) => {
        mouseX = (e.clientX / window.innerWidth - 0.5) * 2;
        mouseY = (e.clientY / window.innerHeight - 0.5) * 2;
    });

    // Resize
    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });

    // Connection threshold
    const connectionDistance = 4.5;
    let frameCount = 0;

    function updateLines() {
        // Remove old lines
        while (linesGroup.children.length > 0) {
            const child = linesGroup.children[0];
            child.geometry.dispose();
            linesGroup.remove(child);
        }

        const pos = pointsGeometry.attributes.position.array;
        for (let i = 0; i < particleCount; i++) {
            for (let j = i + 1; j < particleCount; j++) {
                const dx = pos[i * 3] - pos[j * 3];
                const dy = pos[i * 3 + 1] - pos[j * 3 + 1];
                const dz = pos[i * 3 + 2] - pos[j * 3 + 2];
                const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);

                if (dist < connectionDistance) {
                    const lineGeo = new THREE.BufferGeometry().setFromPoints([
                        new THREE.Vector3(pos[i * 3], pos[i * 3 + 1], pos[i * 3 + 2]),
                        new THREE.Vector3(pos[j * 3], pos[j * 3 + 1], pos[j * 3 + 2])
                    ]);
                    const line = new THREE.Line(lineGeo, linesMaterial);
                    linesGroup.add(line);
                }
            }
        }
    }

    function animate() {
        requestAnimationFrame(animate);
        frameCount++;

        // Move particles
        const pos = pointsGeometry.attributes.position.array;
        for (let i = 0; i < particleCount; i++) {
            pos[i * 3]     += velocities[i].x;
            pos[i * 3 + 1] += velocities[i].y;
            pos[i * 3 + 2] += velocities[i].z;

            // Boundary wrap
            const half = spread / 2;
            if (Math.abs(pos[i * 3])     > half) velocities[i].x *= -1;
            if (Math.abs(pos[i * 3 + 1]) > half) velocities[i].y *= -1;
            if (Math.abs(pos[i * 3 + 2]) > half) velocities[i].z *= -1;
        }
        pointsGeometry.attributes.position.needsUpdate = true;

        // Update lines every 3 frames for performance
        if (frameCount % 3 === 0) {
            updateLines();
        }

        // Subtle camera movement based on mouse
        camera.position.x += (mouseX * 2 - camera.position.x) * 0.02;
        camera.position.y += (-mouseY * 2 - camera.position.y) * 0.02;
        camera.lookAt(scene.position);

        // Slow rotation
        points.rotation.y += 0.0003;
        linesGroup.rotation.y += 0.0003;

        renderer.render(scene, camera);
    }

    updateLines();
    animate();
})();


// ============ SCROLL ANIMATIONS ============
(function initScrollAnimations() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');

                // Trigger axis bar animations
                const bars = entry.target.querySelectorAll('.axis-bar');
                bars.forEach(bar => {
                    const width = bar.getAttribute('data-width');
                    setTimeout(() => {
                        bar.style.width = (width / 35 * 100) + '%';
                    }, 300);
                });
            }
        });
    }, {
        threshold: 0.15,
        rootMargin: '0px 0px -50px 0px'
    });

    document.querySelectorAll('.animate-in').forEach(el => observer.observe(el));
})();


// ============ ANIMATED COUNTERS ============
(function initCounters() {
    const counters = document.querySelectorAll('[data-target]');
    const counterObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && !entry.target.dataset.counted) {
                entry.target.dataset.counted = 'true';
                const target = parseInt(entry.target.getAttribute('data-target'));
                const suffix = entry.target.getAttribute('data-suffix') || '';
                const duration = 2000;
                const startTime = performance.now();

                function updateCounter(currentTime) {
                    const elapsed = currentTime - startTime;
                    const progress = Math.min(elapsed / duration, 1);

                    // Ease out cubic
                    const eased = 1 - Math.pow(1 - progress, 3);
                    const current = Math.round(eased * target);

                    if (target >= 1000) {
                        entry.target.textContent = current.toLocaleString() + suffix;
                    } else {
                        entry.target.textContent = current + suffix;
                    }

                    if (progress < 1) {
                        requestAnimationFrame(updateCounter);
                    }
                }

                requestAnimationFrame(updateCounter);
            }
        });
    }, { threshold: 0.5 });

    counters.forEach(el => counterObserver.observe(el));
})();


// ============ NAVBAR SCROLL EFFECT + FLOATING DEMO ============
(function initNavbar() {
    const navbar = document.getElementById('navbar');
    const floatingDemo = document.getElementById('floating-demo');
    const heroHeight = window.innerHeight * 0.6;

    window.addEventListener('scroll', () => {
        if (window.scrollY > 80) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }

        // Show floating demo button after scrolling past hero
        if (floatingDemo) {
            if (window.scrollY > heroHeight) {
                floatingDemo.classList.add('visible');
            } else {
                floatingDemo.classList.remove('visible');
            }
        }
    });
})();


// ============ SMOOTH SCROLL FOR NAV LINKS ============
(function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const target = document.querySelector(link.getAttribute('href'));
            if (target) {
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    });
})();
