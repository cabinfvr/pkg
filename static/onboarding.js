// pkg | js for onboarding
$(document).ready(function(){let e=null,t=null;function a(){$(".btn-upload, .btn-upload-alt").removeClass("active"),$("#avatar_link").hide(),"file"===e?($("#uploadBtn").addClass("active"),$("#avatar_link").hide()):"url"===e&&($("#urlBtn").addClass("active"),$("#avatar_link").show().focus())}function r(){$("#uploadProgress").hide()}function s(e){$("#avatar_preview").html(`
                    <img src="${e}" alt="Avatar Preview" onerror="this.style.display='none'">
                `)}function i(e,t){let a=`
                    <div class="alert alert-${t}">
                        <i class='bx bx-${"success"===t?"check-circle":"error-circle"}'></i>
                        ${e}
                    </div>
                `,r=$(".messages-container");0===r.length&&(r=$('<div class="messages-container"></div>'),$(".setup-main").prepend(r)),r.html(a),$(".setup-main")[0].scrollIntoView({behavior:"smooth"}),"success"===t&&setTimeout(()=>{r.find(".alert-success").fadeOut()},3e3)}$("#uploadBtn").on("click",function(){e="file",a(),$("#avatar_file").click()}),$("#urlBtn").on("click",function(){e="url",a()}),$("#avatar_file").on("change",function(){let e=this.files[0];if(!e)return;if(!["image/png","image/jpg","image/jpeg","image/gif","image/webp"].includes(e.type)){i("Please select a valid image file (PNG, JPG, JPEG, GIF, or WEBP)","error");return}if(e.size>5242880){i("File size must be less than 5MB","error");return}$("#uploadProgress").show(),$(".progress-fill").css("width","0%"),$(".progress-text").html('<i class="bx bx-loader-alt bx-spin"></i> Uploading...');let a=new FormData;a.append("avatar_file",e),$.ajax({url:"/upload-avatar",type:"POST",data:a,processData:!1,contentType:!1,xhr:function(){let e=new window.XMLHttpRequest;return e.upload.addEventListener("progress",function(e){if(e.lengthComputable){var t;let a=e.loaded/e.total*100;t=a,$(".progress-fill").css("width",t+"%"),$(".progress-text").html(`<i class="bx bx-loader-alt bx-spin"></i> Uploading... ${Math.round(t)}%`)}},!1),e},success:function(e){(console.log("Upload response:",e),e.success)?(t=e.url.signedURL,$("#avatar_link").val(t),s(t),r(),i("Image uploaded successfully!","success")):(r(),i(e.message||"Upload failed","error"))},error:function(e){r();let t=e.responseJSON;i(t?.error||"Upload failed. Please try again.","error")}})}),$("#avatar_link").on("input",function(){let e=this.value.trim();e?s(e):$("#avatar_preview").empty()}),$("#quote").on("input",function(){let e=this.value.length,t=$(".char-counter");t.text(`${e}/450`),e>450?t.css("color","#e74c3c"):e>350?t.css("color","#f39c12"):t.css("color","var(--nc-lk-1)")}),$("#quote").on("input",function(){this.style.height="auto",this.style.height=this.scrollHeight+"px"}),$("#onboardingForm").on("submit",function(e){let t=$("#quote").val(),a=$("#discord_id").val().trim(),r=$("#avatar_link").val().trim(),s=[];if(t.length>20&&s.push("Quote must be less than 20 characters"),a&&!/^\d{17,19}$/.test(a)&&s.push("Discord ID must be 17-19 digits long"),r&&!function e(t){try{return new URL(t),!0}catch(a){return!1}}(r)&&s.push("Please enter a valid URL for your profile picture"),s.length>0)return e.preventDefault(),i(s.join("<br>"),"error"),!1;let n=$(this).find('button[type="submit"]');n.html('<i class="bx bx-loader-alt bx-spin"></i> Setting up profile...'),n.prop("disabled",!0)}),$(".input-field").on("focus",function(){$(this).parent().addClass("input-focused")}).on("blur",function(){$(this).parent().removeClass("input-focused")})});const style=document.createElement("style");style.textContent=`
            .highlight-input {
                animation: highlight 2s ease;
            }
            
            @keyframes highlight {
                0% { border-color: var(--nc-bg-3); }
                50% { border-color: var(--nc-lk-1); box-shadow: 0 0 0 3px rgba(var(--nc-lk-1), 0.2); }
                100% { border-color: var(--nc-bg-3); }
            }
            
            .input-focused label {
                color: var(--nc-lk-1);
                transform: translateY(-2px);
                transition: all 0.2s ease;
            }
            
            .bx-spin {
                animation: spin 1s linear infinite;
            }
            
            @keyframes spin {
                from { transform: rotate(0deg); }
                to { transform: rotate(360deg); }
            }
        `,document.head.appendChild(style);